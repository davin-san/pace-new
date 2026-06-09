#ifndef __PACE_COMPAT_MESSAGE_HH__
#define __PACE_COMPAT_MESSAGE_HH__

#include <cstdint>
#include <iostream>
#include <memory>

#include "base/types.hh"
#include "mem/ruby/common/NetDest.hh"

namespace gem5
{
namespace ruby
{

class Message;
using MsgPtr = std::shared_ptr<Message>;

class Message
{
  public:
    Message() = default;
    Message(const NetDest& dest, int size, Tick time)
        : _destination(dest), _size(size), _time(time),
          _creation_time(time)
    {}

    MsgPtr clone() const
    {
        auto copy = std::make_shared<Message>(*this);
        copy->_network_enqueue_time = gem5::curTick();
        copy->_has_network_enqueue_time = true;
        copy->_has_network_latency = false;
        return copy;
    }
    NetDest& getDestination() { return _destination; }
    const NetDest& getDestination() const { return _destination; }
    int getMessageSize() const { return _size; }
    Tick getTime() const { return _time; }
    void setTime(Tick time) { _time = time; }
    Tick getCreationTime() const { return _creation_time; }
    int getTrafficOrigin() const { return _traffic_origin; }
    void setTrafficOrigin(int origin) { _traffic_origin = origin; }
    int getTrafficRequestVnet() const { return _traffic_request_vnet; }
    void setTrafficRequestVnet(int vnet) { _traffic_request_vnet = vnet; }
    bool shouldGenerateTrafficResponse() const
    {
        return _generate_traffic_response;
    }
    void setGenerateTrafficResponse(bool generate)
    {
        _generate_traffic_response = generate;
    }
    bool hasNetworkEnqueueTime() const { return _has_network_enqueue_time; }
    bool hasNetworkLatency() const { return _has_network_latency; }
    Tick getNetworkLatency() const { return _network_latency; }
    void setNetworkDequeueTime(Tick time)
    {
        if (!_has_network_enqueue_time || _has_network_latency) {
            return;
        }
        _network_latency = time > _network_enqueue_time ?
            time - _network_enqueue_time - 1 : 0;
        _has_network_latency = true;
    }

    bool functionalRead(Packet*, WriteMask&) { return false; }
    bool functionalWrite(Packet*) { return false; }

    void print(std::ostream& out) const { out << "[Message]"; }

  private:
    NetDest _destination;
    int _size = 0;
    Tick _time = 0;
    Tick _creation_time = 0;
    int _traffic_origin = -1;
    int _traffic_request_vnet = -1;
    bool _generate_traffic_response = false;
    Tick _network_enqueue_time = 0;
    Tick _network_latency = 0;
    bool _has_network_enqueue_time = false;
    bool _has_network_latency = false;
};

inline std::ostream& operator<<(std::ostream& out, const Message& msg)
{
    msg.print(out);
    return out;
}

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_MESSAGE_HH__
