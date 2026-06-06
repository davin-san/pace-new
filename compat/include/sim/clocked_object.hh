#ifndef __PACE_COMPAT_CLOCKED_OBJECT_HH__
#define __PACE_COMPAT_CLOCKED_OBJECT_HH__

#include "sim/sim_object.hh"

namespace gem5
{

class ClockedObject : public SimObject
{
  public:
    struct Params : public SimObject::Params {
        Tick clock_period = 1;
    };

    ClockedObject() : SimObject(), _clock_period(1) {}
    explicit ClockedObject(const Params& p)
        : SimObject(p), _clock_period(p.clock_period)
    {}

    Tick clockEdge(Cycles cycles = 0) const { return curTick() + cycles; }
    Tick cyclesToTicks(Cycles cycles) const { return cycles; }
    Cycles curCycle() const { return curTick(); }
    Tick clockPeriod() const { return _clock_period; }
    bool alreadyScheduled(Tick when) const;

    virtual void wakeup() {}

  private:
    Tick _clock_period;
};

} // namespace gem5

#endif // __PACE_COMPAT_CLOCKED_OBJECT_HH__
