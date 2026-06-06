#!/usr/bin/env python3
"""Exercise the standalone event queue paths used by Garnet wakeups."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verif" / "out" / "event_queue_test"


SOURCE = r'''
#include <iostream>
#include <string>
#include <vector>

#include "pace_compat/EventQueue.hh"

class Recorder : public gem5::ClockedObject
{
  public:
    Recorder(const std::string& name, std::vector<std::string>& log)
        : gem5::ClockedObject(makeParams(name)), _log(log)
    {}

    void wakeup() override
    {
        _log.push_back(name() + "@" + std::to_string(gem5::curTick()));
    }

  private:
    std::vector<std::string>& _log;

    static gem5::ClockedObject::Params makeParams(const std::string& name)
    {
        gem5::ClockedObject::Params params;
        params.name = name;
        return params;
    }
};

class SchedulingRecorder : public gem5::ClockedObject
{
  public:
    SchedulingRecorder(const std::string& name, gem5::ClockedObject* next,
                       std::vector<std::string>& log)
        : gem5::ClockedObject(makeParams(name)), _next(next), _log(log)
    {}

    void wakeup() override
    {
        _log.push_back(name() + "@" + std::to_string(gem5::curTick()));
        gem5::eventQueue().schedule(_next, gem5::curTick());
    }

  private:
    gem5::ClockedObject* _next;
    std::vector<std::string>& _log;

    static gem5::ClockedObject::Params makeParams(const std::string& name)
    {
        gem5::ClockedObject::Params params;
        params.name = name;
        return params;
    }
};

int main()
{
    std::vector<std::string> log;
    Recorder net("int_net0", log);
    Recorder router("router0", log);
    Recorder ni("network_interface0", log);
    Recorder credit("int_credit0", log);

    gem5::eventQueue().setCurTick(0);
    gem5::eventQueue().schedule(&credit, 300);
    gem5::eventQueue().schedule(&router, 300);
    gem5::eventQueue().schedule(&net, 300);
    gem5::eventQueue().schedule(&ni, 300);
    gem5::eventQueue().schedule(&ni, 300);
    if (!gem5::eventQueue().scheduled(&ni, 300)) {
        std::cerr << "scheduled() failed for far event\n";
        return 1;
    }

    gem5::eventQueue().setCurTick(300);
    gem5::eventQueue().process();

    const std::vector<std::string> expected_far = {
        "int_net0@300",
        "router0@300",
        "network_interface0@300",
        "int_credit0@300",
    };
    if (log != expected_far) {
        std::cerr << "far event priority mismatch\n";
        for (const auto& item : log) std::cerr << item << "\n";
        return 1;
    }

    log.clear();
    Recorder child("network_interface_child", log);
    SchedulingRecorder parent("router_parent", &child, log);
    gem5::eventQueue().schedule(&parent, 301);
    gem5::eventQueue().setCurTick(301);
    gem5::eventQueue().process();

    const std::vector<std::string> expected_same_tick = {
        "router_parent@301",
        "network_interface_child@301",
    };
    if (log != expected_same_tick) {
        std::cerr << "same tick reschedule mismatch\n";
        for (const auto& item : log) std::cerr << item << "\n";
        return 1;
    }

    return 0;
}
'''


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    src = OUT / "event_queue_test.cc"
    binary = OUT / "event_queue_test"
    src.write_text(SOURCE)
    compile_cmd = [
        "g++",
        "-std=c++17",
        "-O2",
        "-Icompat/include",
        "-I.",
        str(src),
        "compat/src/EventQueue.cc",
        "compat/src/Trace.cc",
        "-o",
        str(binary),
    ]
    proc = subprocess.run(
        compile_cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        return proc.returncode
    run = subprocess.run(
        [str(binary)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if run.returncode != 0:
        print(run.stdout)
    else:
        print("event_queue: PASS")
    return run.returncode


if __name__ == "__main__":
    sys.exit(main())
