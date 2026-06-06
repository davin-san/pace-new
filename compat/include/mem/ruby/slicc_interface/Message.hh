#ifndef __PACE_COMPAT_MESSAGE_HH__
#define __PACE_COMPAT_MESSAGE_HH__

#include <cstdint>
#include <iostream>
#include <memory>

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

    MsgPtr clone() const { return std::make_shared<Message>(*this); }
    NetDest& getDestination() { return _destination; }
    const NetDest& getDestination() const { return _destination; }
    int getMessageSize() const { return _size; }
    Tick getTime() const { return _time; }
    void setTime(Tick time) { _time = time; }
    Tick getCreationTime() const { return _creation_time; }

    bool functionalRead(Packet*, WriteMask&) { return false; }
    bool functionalWrite(Packet*) { return false; }

    void print(std::ostream& out) const { out << "[Message]"; }

  private:
    NetDest _destination;
    int _size = 0;
    Tick _time = 0;
    Tick _creation_time = 0;
};

inline std::ostream& operator<<(std::ostream& out, const Message& msg)
{
    msg.print(out);
    return out;
}

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_MESSAGE_HH__
