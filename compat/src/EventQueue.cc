#include "pace_compat/EventQueue.hh"

namespace gem5
{

EventQueue&
eventQueue()
{
    static EventQueue queue;
    return queue;
}

Tick
curTick()
{
    return eventQueue().getCurTick();
}

bool
ClockedObject::alreadyScheduled(Tick when) const
{
    return eventQueue().scheduled(const_cast<ClockedObject*>(this), when);
}

} // namespace gem5
