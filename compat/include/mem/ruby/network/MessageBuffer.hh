#ifndef __PACE_COMPAT_MESSAGE_BUFFER_HH__
#define __PACE_COMPAT_MESSAGE_BUFFER_HH__

#include <deque>
#include <functional>

#include "mem/ruby/common/Consumer.hh"
#include "mem/ruby/slicc_interface/Message.hh"
#include "pace_compat/Trace.hh"

namespace gem5
{
namespace ruby
{

class MessageBuffer
{
  public:
    MessageBuffer() : _id(_next_id++) {}

    void setConsumer(Consumer* consumer)
    {
        _consumer = consumer;
        if (pace::traceEnabled()) {
            pace::traceEvent("message_buffer.set_consumer", {
                {"buffer", pace::traceValue(_id)},
                {"consumer", pace::traceValue(
                    consumer && consumer->getObject() ?
                        consumer->getObject()->name() : "")},
            });
        }
    }

    bool isReady(Tick curTime) const
    {
        return !_queue.empty() && _queue.front().ready <= curTime;
    }

    MsgPtr peekMsgPtr() const { return _queue.front().message; }
    bool empty() const { return _queue.empty(); }
    size_t size() const { return _queue.size(); }

    void dequeue(Tick curTime)
    {
        auto message = _queue.front().message;
        if (pace::traceEnabled()) {
            pace::traceEvent("message_buffer.dequeue", {
                {"buffer", pace::traceValue(_id)},
                {"ready", pace::traceValue(_queue.front().ready)},
                {"cur_time", pace::traceValue(curTime)},
                {"message_size", pace::traceValue(message->getMessageSize())},
                {"dest_count", pace::traceValue(
                    message->getDestination().getAllDest().size())},
            });
        }
        _queue.pop_front();
        if (_callback) {
            _callback();
        }
    }

    MsgPtr dequeueMsg(Tick curTime)
    {
        MsgPtr message = peekMsgPtr();
        dequeue(curTime);
        return message;
    }

    void enqueue(MsgPtr message, Tick curTime, Tick delta, ClockedObject*)
    {
        message->setTime(curTime);
        _queue.push_back({message, curTime + delta});
        if (pace::traceEnabled()) {
            pace::traceEvent("message_buffer.enqueue", {
                {"buffer", pace::traceValue(_id)},
                {"cur_time", pace::traceValue(curTime)},
                {"ready", pace::traceValue(curTime + delta)},
                {"message_size", pace::traceValue(message->getMessageSize())},
                {"dest_count", pace::traceValue(
                    message->getDestination().getAllDest().size())},
            });
        }
        if (_consumer) {
            _consumer->scheduleEventAbsolute(curTime + delta);
        }
    }

    void enqueue(MsgPtr message, Tick curTime, Tick delta, bool, bool)
    {
        enqueue(message, curTime, delta, nullptr);
    }

    bool areNSlotsAvailable(int, Tick) const { return true; }
    void registerDequeueCallback(std::function<void()> cb) { _callback = cb; }
    void unregisterDequeueCallback() { _callback = nullptr; }

  private:
    struct Entry {
        MsgPtr message;
        Tick ready;
    };

    std::deque<Entry> _queue;
    Consumer* _consumer = nullptr;
    std::function<void()> _callback;
    size_t _id;
    inline static size_t _next_id = 0;
};

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_MESSAGE_BUFFER_HH__
