#!/usr/bin/env python3
"""Apply or restore reversible gem5 PACE_TRACE instrumentation.

This intentionally edits the gem5 source tree used for trace builds only. It
never edits pace-new/src, so the production Garnet byte-identity gate remains
meaningful.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


MARKER = "PACE_TRACE_INSTRUMENTATION"
BACKUP_SUFFIX = ".pace_trace.bak"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["apply", "restore", "status"])
    parser.add_argument("gem5_root", type=Path)
    args = parser.parse_args()

    gem5_root = args.gem5_root.resolve()
    files = _files(gem5_root)

    if args.action == "status":
        for path in files:
            state = "patched" if MARKER in path.read_text() else "clean"
            backup = "backup" if _backup(path).exists() else "no-backup"
            print(f"{path.relative_to(gem5_root)}: {state}, {backup}")
        return 0

    if args.action == "restore":
        for path in files:
            backup = _backup(path)
            if backup.exists():
                shutil.copyfile(backup, path)
                backup.unlink()
                print(f"restored {path.relative_to(gem5_root)}")
        return 0

    for path in files:
        text = path.read_text()
        if MARKER in text:
            print(f"already patched {path.relative_to(gem5_root)}")
            continue
        backup = _backup(path)
        if not backup.exists():
            shutil.copyfile(path, backup)
        patched = PATCHERS[path.relative_to(gem5_root).as_posix()](text)
        path.write_text(patched)
        print(f"patched {path.relative_to(gem5_root)}")
    return 0


def _files(gem5_root: Path) -> list[Path]:
    return [gem5_root / relative for relative in PATCHERS]


def _backup(path: Path) -> Path:
    return path.with_name(path.name + BACKUP_SUFFIX)


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"expected one match for {label}, found {text.count(old)}")
    return text.replace(old, new, 1)


def _patch_synthetic(text: str) -> str:
    text = _replace_once(
        text,
        """    DPRINTF(GarnetSyntheticTraffic,
            "Completed injection of %s packet for address %x\\n",
            pkt->isWrite() ? "write" : "read\\n",
            pkt->req->getPaddr());
""",
        """    DPRINTF(GarnetSyntheticTraffic,
            "Completed injection of %s packet for address %x\\n",
            pkt->isWrite() ? "write" : "read\\n",
            pkt->req->getPaddr());
    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(GarnetSyntheticTraffic,
            "PACE_TRACE {\\"event\\":\\"traffic.deliver\\","
            "\\"tick\\":%llu,\\"source\\":%d,\\"addr\\":%llu,"
            "\\"is_write\\":%d}\\n",
            (unsigned long long)curTick(), id,
            (unsigned long long)pkt->req->getPaddr(), pkt->isWrite());
""",
        "synthetic completeRequest",
    )
    text = _replace_once(
        text,
        """    DPRINTF(GarnetSyntheticTraffic,
            "Generated packet with destination %d, embedded in address %x\\n",
            destination, req->getPaddr());

    PacketPtr pkt = new Packet(req, requestType);
""",
        """    DPRINTF(GarnetSyntheticTraffic,
            "Generated packet with destination %d, embedded in address %x\\n",
            destination, req->getPaddr());
    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(GarnetSyntheticTraffic,
            "PACE_TRACE {\\"event\\":\\"traffic.inject\\","
            "\\"tick\\":%llu,\\"source\\":%d,\\"destination\\":%u,"
            "\\"vnet\\":%d,\\"addr\\":%llu,\\"request_type\\":%d}\\n",
            (unsigned long long)curTick(), id, destination, injReqType,
            (unsigned long long)req->getPaddr(), requestType);

    PacketPtr pkt = new Packet(req, requestType);
""",
        "synthetic generatePkt",
    )
    return text


def _patch_message_buffer(text: str) -> str:
    text = _replace_once(
        text,
        '#include "debug/RubyQueue.hh"\n',
        '#include "debug/RubyQueue.hh"\n#include "debug/RubyNetwork.hh" // PACE_TRACE_INSTRUMENTATION\n',
        "message buffer include",
    )
    text = _replace_once(
        text,
        """    DPRINTF(RubyQueue, "Enqueue arrival_time: %lld, Message: %s\\n",
            arrival_time, *(message.get()));

    // Schedule the wakeup
""",
        """    DPRINTF(RubyQueue, "Enqueue arrival_time: %lld, Message: %s\\n",
            arrival_time, *(message.get()));
    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"message_buffer.enqueue\\","
            "\\"tick\\":%llu,\\"buffer\\":\\"%s\\","
            "\\"current_time\\":%llu,\\"arrival_time\\":%llu,"
            "\\"msg_counter\\":%llu}\\n",
            (unsigned long long)curTick(), name().c_str(),
            (unsigned long long)current_time,
            (unsigned long long)arrival_time,
            (unsigned long long)m_msg_counter);

    // Schedule the wakeup
""",
        "message buffer enqueue",
    )
    text = _replace_once(
        text,
        """    // get the delay cycles
    message->updateDelayedTicks(current_time);
    Tick delay = message->getDelayedTicks();

    // record previous size and time so the current buffer size isn't
""",
        """    // get the delay cycles
    message->updateDelayedTicks(current_time);
    Tick delay = message->getDelayedTicks();
    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"message_buffer.dequeue\\","
            "\\"tick\\":%llu,\\"buffer\\":\\"%s\\","
            "\\"current_time\\":%llu,\\"delayed_ticks\\":%llu}\\n",
            (unsigned long long)curTick(), name().c_str(),
            (unsigned long long)current_time,
            (unsigned long long)delay);

    // record previous size and time so the current buffer size isn't
""",
        "message buffer dequeue",
    )
    return text


def _patch_network_interface(text: str) -> str:
    text = _replace_once(
        text,
        """                    outNode_ptr[vnet]->enqueue(t_flit->get_msg_ptr(), curTime,
                                               cyclesToTicks(Cycles(1)),
                                               m_net_ptr->getRandomization(),
                                               m_net_ptr->getWarmupEnabled());

                    // Simply send a credit back since we are not buffering
""",
        """                    // PACE_TRACE_INSTRUMENTATION
                    DPRINTF(RubyNetwork,
                            "PACE_TRACE {\\"event\\":\\"ni.eject\\","
                            "\\"tick\\":%llu,\\"ni\\":%d,\\"vnet\\":%d,"
                            "\\"vc\\":%d,\\"packet_id\\":%d,\\"flit_id\\":%d,"
                            "\\"flit_type\\":%d}\\n",
                            (unsigned long long)curTick(), m_id, vnet,
                            t_flit->get_vc(), t_flit->getPacketID(),
                            t_flit->get_id(), t_flit->get_type());
                    outNode_ptr[vnet]->enqueue(t_flit->get_msg_ptr(), curTime,
                                               cyclesToTicks(Cycles(1)),
                                               m_net_ptr->getRandomization(),
                                               m_net_ptr->getWarmupEnabled());

                    // Simply send a credit back since we are not buffering
""",
        "network interface ejection",
    )
    text = _replace_once(
        text,
        """            niOutVcs[vc].insert(fl);
        }

        m_ni_out_vcs_enqueue_time[vc] = curTick();
""",
        """            niOutVcs[vc].insert(fl);
        }
        // PACE_TRACE_INSTRUMENTATION
        DPRINTF(RubyNetwork,
                "PACE_TRACE {\\"event\\":\\"ni.flitisize\\","
                "\\"tick\\":%llu,\\"ni\\":%d,\\"src_router\\":%d,"
                "\\"dest_ni\\":%d,\\"dest_router\\":%d,\\"vnet\\":%d,"
                "\\"vc\\":%d,\\"packet_id\\":%d,\\"num_flits\\":%d,"
                "\\"message_size\\":%d}\\n",
                (unsigned long long)curTick(), m_id, route.src_router,
                route.dest_ni, route.dest_router, vnet, vc, packet_id,
                num_flits, m_net_ptr->MessageSizeType_to_int(
                net_msg_ptr->getMessageSize()));

        m_ni_out_vcs_enqueue_time[vc] = curTick();
""",
        "network interface flitisize",
    )
    return text


def _patch_router(text: str) -> str:
    text = _replace_once(
        text,
        """void
Router::wakeup()
{
    DPRINTF(RubyNetwork, "Router %d woke up\\n", m_id);
    assert(clockEdge() == curTick());
""",
        """void
Router::wakeup()
{
    DPRINTF(RubyNetwork, "Router %d woke up\\n", m_id);
    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"router.wakeup\\","
            "\\"tick\\":%llu,\\"router\\":%d,\\"inports\\":%llu,"
            "\\"outports\\":%llu}\\n",
            (unsigned long long)curTick(), m_id,
            (unsigned long long)m_input_unit.size(),
            (unsigned long long)m_output_unit.size());
    assert(clockEdge() == curTick());
""",
        "router wakeup",
    )
    text = _replace_once(
        text,
        """void
Router::schedule_wakeup(Cycles time)
{
    // wake up after time cycles
    scheduleEvent(time);
}
""",
        """void
Router::schedule_wakeup(Cycles time)
{
    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"router.schedule\\","
            "\\"tick\\":%llu,\\"router\\":%d,\\"cycles\\":%llu,"
            "\\"when\\":%llu}\\n",
            (unsigned long long)curTick(), m_id,
            (unsigned long long)time,
            (unsigned long long)clockEdge(time));
    // wake up after time cycles
    scheduleEvent(time);
}
""",
        "router schedule_wakeup",
    )
    return text


def _patch_input_unit(text: str) -> str:
    text = _replace_once(
        text,
        """        int vc = t_flit->get_vc();
        t_flit->increment_hops(); // for stats
""",
        """        int vc = t_flit->get_vc();
        // PACE_TRACE_INSTRUMENTATION
        DPRINTF(RubyNetwork,
                "PACE_TRACE {\\"event\\":\\"input.flit\\","
                "\\"tick\\":%llu,\\"router\\":%d,\\"inport\\":%d,"
                "\\"vc\\":%d,\\"vnet\\":%d,\\"packet_id\\":%d,"
                "\\"flit_id\\":%d,\\"flit_type\\":%d}\\n",
                (unsigned long long)curTick(), m_router->get_id(), m_id,
                vc, t_flit->get_vnet(), t_flit->getPacketID(),
                t_flit->get_id(), t_flit->get_type());
        t_flit->increment_hops(); // for stats
""",
        "input flit",
    )
    text = _replace_once(
        text,
        """            int outport = m_router->route_compute(t_flit->get_route(),
                m_id, m_direction);

            // Update output port in VC
""",
        """            int outport = m_router->route_compute(t_flit->get_route(),
                m_id, m_direction);
            // PACE_TRACE_INSTRUMENTATION
            DPRINTF(RubyNetwork,
                    "PACE_TRACE {\\"event\\":\\"input.route_compute\\","
                    "\\"tick\\":%llu,\\"router\\":%d,\\"inport\\":%d,"
                    "\\"vc\\":%d,\\"vnet\\":%d,\\"packet_id\\":%d,"
                    "\\"dest_ni\\":%d,\\"dest_router\\":%d,"
                    "\\"outport\\":%d}\\n",
                    (unsigned long long)curTick(), m_router->get_id(), m_id,
                    vc, t_flit->get_vnet(), t_flit->getPacketID(),
                    t_flit->get_route().dest_ni,
                    t_flit->get_route().dest_router, outport);

            // Update output port in VC
""",
        "input route compute",
    )
    text = _replace_once(
        text,
        """        virtualChannels[vc].insertFlit(t_flit);

        int vnet = vc/m_vc_per_vnet;
""",
        """        virtualChannels[vc].insertFlit(t_flit);
        // PACE_TRACE_INSTRUMENTATION
        DPRINTF(RubyNetwork,
                "PACE_TRACE {\\"event\\":\\"input.buffer_insert\\","
                "\\"tick\\":%llu,\\"router\\":%d,\\"inport\\":%d,"
                "\\"vc\\":%d,\\"vnet\\":%d,\\"packet_id\\":%d,"
                "\\"flit_id\\":%d}\\n",
                (unsigned long long)curTick(), m_router->get_id(), m_id,
                vc, t_flit->get_vnet(), t_flit->getPacketID(),
                t_flit->get_id());

        int vnet = vc/m_vc_per_vnet;
""",
        "input buffer insert",
    )
    text = _replace_once(
        text,
        """    Credit *t_credit = new Credit(in_vc, free_signal, curTime);
    creditQueue.insert(t_credit);
""",
        """    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"credit.send\\","
            "\\"tick\\":%llu,\\"router\\":%d,\\"inport\\":%d,"
            "\\"vc\\":%d,\\"free\\":%d}\\n",
            (unsigned long long)curTick(), m_router->get_id(), m_id,
            in_vc, free_signal);
    Credit *t_credit = new Credit(in_vc, free_signal, curTime);
    creditQueue.insert(t_credit);
""",
        "input credit send",
    )
    return text


def _patch_switch_allocator(text: str) -> str:
    text = _replace_once(
        text,
        """void
SwitchAllocator::wakeup()
{
    arbitrate_inports(); // First stage of allocation
""",
        """void
SwitchAllocator::wakeup()
{
    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"sa.wakeup\\","
            "\\"tick\\":%llu,\\"router\\":%d}\\n",
            (unsigned long long)curTick(), m_router->get_id());
    arbitrate_inports(); // First stage of allocation
""",
        "switch allocator wakeup",
    )
    text = _replace_once(
        text,
        """                if (make_request) {
                    m_input_arbiter_activity++;
                    m_port_requests[inport] = outport;
                    m_vc_winners[inport] = invc;

                    break; // got one vc winner for this port
                }
""",
        """                if (make_request) {
                    // PACE_TRACE_INSTRUMENTATION
                    DPRINTF(RubyNetwork,
                            "PACE_TRACE {\\"event\\":\\"sa.request\\","
                            "\\"tick\\":%llu,\\"router\\":%d,"
                            "\\"inport\\":%d,\\"invc\\":%d,"
                            "\\"outport\\":%d,\\"outvc\\":%d,"
                            "\\"vnet\\":%d}\\n",
                            (unsigned long long)curTick(),
                            m_router->get_id(), inport, invc, outport,
                            outvc, get_vnet(invc));
                    m_input_arbiter_activity++;
                    m_port_requests[inport] = outport;
                    m_vc_winners[inport] = invc;

                    break; // got one vc winner for this port
                }
""",
        "switch allocator request",
    )
    text = _replace_once(
        text,
        """                // decrement credit in outvc
                output_unit->decrement_credit(outvc);

                // flit ready for Switch Traversal
""",
        """                // PACE_TRACE_INSTRUMENTATION
                DPRINTF(RubyNetwork,
                        "PACE_TRACE {\\"event\\":\\"sa.grant\\","
                        "\\"tick\\":%llu,\\"router\\":%d,"
                        "\\"inport\\":%d,\\"invc\\":%d,"
                        "\\"outport\\":%d,\\"outvc\\":%d,"
                        "\\"vnet\\":%d,\\"packet_id\\":%d,"
                        "\\"flit_id\\":%d,\\"flit_type\\":%d}\\n",
                        (unsigned long long)curTick(), m_router->get_id(),
                        inport, invc, outport, outvc, get_vnet(invc),
                        t_flit->getPacketID(), t_flit->get_id(),
                        t_flit->get_type());

                // decrement credit in outvc
                output_unit->decrement_credit(outvc);

                // flit ready for Switch Traversal
""",
        "switch allocator grant",
    )
    text = _replace_once(
        text,
        """    assert(outvc != -1);
    m_router->getInputUnit(inport)->grant_outvc(invc, outvc);
    return outvc;
""",
        """    assert(outvc != -1);
    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"vc.allocate\\","
            "\\"tick\\":%llu,\\"router\\":%d,\\"outport\\":%d,"
            "\\"inport\\":%d,\\"invc\\":%d,\\"outvc\\":%d,"
            "\\"vnet\\":%d}\\n",
            (unsigned long long)curTick(), m_router->get_id(), outport,
            inport, invc, outvc, get_vnet(invc));
    m_router->getInputUnit(inport)->grant_outvc(invc, outvc);
    return outvc;
""",
        "vc allocate",
    )
    return text


def _patch_crossbar(text: str) -> str:
    text = _replace_once(
        text,
        """            // This will take care of waking up the Network Link
            // in the next cycle
            m_router->getOutputUnit(outport)->insert_flit(t_flit);
""",
        """            // PACE_TRACE_INSTRUMENTATION
            DPRINTF(RubyNetwork,
                    "PACE_TRACE {\\"event\\":\\"crossbar.traverse\\","
                    "\\"tick\\":%llu,\\"router\\":%d,\\"outport\\":%d,"
                    "\\"vc\\":%d,\\"vnet\\":%d,\\"packet_id\\":%d,"
                    "\\"flit_id\\":%d,\\"flit_type\\":%d}\\n",
                    (unsigned long long)curTick(), m_router->get_id(),
                    outport, t_flit->get_vc(), t_flit->get_vnet(),
                    t_flit->getPacketID(), t_flit->get_id(),
                    t_flit->get_type());
            // This will take care of waking up the Network Link
            // in the next cycle
            m_router->getOutputUnit(outport)->insert_flit(t_flit);
""",
        "crossbar traverse",
    )
    return text


def _patch_output_unit(text: str) -> str:
    text = _replace_once(
        text,
        """    outVcState[out_vc].decrement_credit();
}
""",
        """    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"credit.decrement\\","
            "\\"tick\\":%llu,\\"router\\":%d,\\"outport\\":%d,"
            "\\"outvc\\":%d,\\"credit_before\\":%d}\\n",
            (unsigned long long)curTick(), m_router->get_id(), m_id,
            out_vc, outVcState[out_vc].get_credit_count());
    outVcState[out_vc].decrement_credit();
}
""",
        "output decrement credit",
    )
    text = _replace_once(
        text,
        """    outVcState[out_vc].increment_credit();
}
""",
        """    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"credit.increment\\","
            "\\"tick\\":%llu,\\"router\\":%d,\\"outport\\":%d,"
            "\\"outvc\\":%d,\\"credit_before\\":%d}\\n",
            (unsigned long long)curTick(), m_router->get_id(), m_id,
            out_vc, outVcState[out_vc].get_credit_count());
    outVcState[out_vc].increment_credit();
}
""",
        "output increment credit",
    )
    text = _replace_once(
        text,
        """        Credit *t_credit = (Credit*) m_credit_link->consumeLink();
        increment_credit(t_credit->get_vc());

        if (t_credit->is_free_signal())
""",
        """        Credit *t_credit = (Credit*) m_credit_link->consumeLink();
        // PACE_TRACE_INSTRUMENTATION
        DPRINTF(RubyNetwork,
                "PACE_TRACE {\\"event\\":\\"credit.receive\\","
                "\\"tick\\":%llu,\\"router\\":%d,\\"outport\\":%d,"
                "\\"vc\\":%d,\\"free\\":%d}\\n",
                (unsigned long long)curTick(), m_router->get_id(), m_id,
                t_credit->get_vc(), t_credit->is_free_signal());
        increment_credit(t_credit->get_vc());

        if (t_credit->is_free_signal())
""",
        "output credit receive",
    )
    text = _replace_once(
        text,
        """    outBuffer.insert(t_flit);
    m_out_link->scheduleEventAbsolute(m_router->clockEdge(Cycles(1)));
}
""",
        """    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"output.flit_enqueue\\","
            "\\"tick\\":%llu,\\"router\\":%d,\\"outport\\":%d,"
            "\\"vc\\":%d,\\"vnet\\":%d,\\"packet_id\\":%d,"
            "\\"flit_id\\":%d,\\"flit_type\\":%d}\\n",
            (unsigned long long)curTick(), m_router->get_id(), m_id,
            t_flit->get_vc(), t_flit->get_vnet(), t_flit->getPacketID(),
            t_flit->get_id(), t_flit->get_type());
    outBuffer.insert(t_flit);
    m_out_link->scheduleEventAbsolute(m_router->clockEdge(Cycles(1)));
}
""",
        "output flit enqueue",
    )
    return text


def _patch_network_link(text: str) -> str:
    text = _replace_once(
        text,
        """        t_flit->set_time(clockEdge(m_latency));
        linkBuffer.insert(t_flit);
""",
        """        // PACE_TRACE_INSTRUMENTATION
        DPRINTF(RubyNetwork,
                "PACE_TRACE {\\"event\\":\\"link.transfer\\","
                "\\"tick\\":%llu,\\"link\\":\\"%s\\","
                "\\"link_id\\":%d,\\"src\\":\\"%s\\","
                "\\"arrival\\":%llu,\\"vc\\":%d,\\"vnet\\":%d,"
                "\\"packet_id\\":%d,\\"flit_id\\":%d,"
                "\\"flit_type\\":%d}\\n",
                (unsigned long long)curTick(), name().c_str(), m_id,
                src_object->name().c_str(),
                (unsigned long long)clockEdge(m_latency),
                t_flit->get_vc(), t_flit->get_vnet(),
                t_flit->getPacketID(), t_flit->get_id(),
                t_flit->get_type());
        t_flit->set_time(clockEdge(m_latency));
        linkBuffer.insert(t_flit);
""",
        "network link transfer",
    )
    return text


def _patch_routing_unit(text: str) -> str:
    text = _replace_once(
        text,
        """    assert(outport != -1);
    return outport;
}
""",
        """    assert(outport != -1);
    // PACE_TRACE_INSTRUMENTATION
    DPRINTF(RubyNetwork,
            "PACE_TRACE {\\"event\\":\\"routing.outport\\","
            "\\"tick\\":%llu,\\"router\\":%d,\\"vnet\\":%d,"
            "\\"src_ni\\":%d,\\"src_router\\":%d,\\"dest_ni\\":%d,"
            "\\"dest_router\\":%d,\\"inport\\":%d,"
            "\\"outport\\":%d,\\"algorithm\\":%d}\\n",
            (unsigned long long)curTick(), m_router->get_id(), route.vnet,
            route.src_ni, route.src_router, route.dest_ni,
            route.dest_router, inport, outport, routing_algorithm);
    return outport;
}
""",
        "routing unit outport",
    )
    return text


PATCHERS = {
    "src/cpu/testers/garnet_synthetic_traffic/GarnetSyntheticTraffic.cc":
        _patch_synthetic,
    "src/mem/ruby/network/MessageBuffer.cc": _patch_message_buffer,
    "src/mem/ruby/network/garnet/NetworkInterface.cc":
        _patch_network_interface,
    "src/mem/ruby/network/garnet/Router.cc": _patch_router,
    "src/mem/ruby/network/garnet/InputUnit.cc": _patch_input_unit,
    "src/mem/ruby/network/garnet/SwitchAllocator.cc":
        _patch_switch_allocator,
    "src/mem/ruby/network/garnet/CrossbarSwitch.cc": _patch_crossbar,
    "src/mem/ruby/network/garnet/OutputUnit.cc": _patch_output_unit,
    "src/mem/ruby/network/garnet/NetworkLink.cc": _patch_network_link,
    "src/mem/ruby/network/garnet/RoutingUnit.cc": _patch_routing_unit,
}


if __name__ == "__main__":
    raise SystemExit(main())
