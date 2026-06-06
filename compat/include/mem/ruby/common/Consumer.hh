#ifndef __PACE_COMPAT_CONSUMER_HH__
#define __PACE_COMPAT_CONSUMER_HH__

#include "pace_compat/EventQueue.hh"
#include "sim/clocked_object.hh"

namespace gem5
{
namespace ruby
{

class Consumer
{
  public:
    explicit Consumer(ClockedObject* object = nullptr) : _object(object) {}
    virtual ~Consumer() = default;

    void scheduleEvent(Cycles cycles)
    {
        eventQueue().schedule(_object, _object->clockEdge(cycles));
    }

    void scheduleEventAbsolute(Tick when)
    {
        eventQueue().schedule(_object, when);
    }

    ClockedObject* getObject() const { return _object; }

  private:
    ClockedObject* _object;
};

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_CONSUMER_HH__
