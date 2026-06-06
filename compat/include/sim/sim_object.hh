#ifndef __PACE_COMPAT_SIM_OBJECT_HH__
#define __PACE_COMPAT_SIM_OBJECT_HH__

#include <cstdlib>
#include <cstdio>
#include <iostream>
#include <string>

#include "base/types.hh"

#define PARAMS(type) typedef type##Params Params

#define fatal(...) do { std::fprintf(stderr, __VA_ARGS__); std::fprintf(stderr, "\n"); std::abort(); } while (0)
#define panic(...) fatal(__VA_ARGS__)
#define fatal_if(cond, ...) do { if (cond) fatal(__VA_ARGS__); } while (0)
#define panic_if(cond, ...) fatal_if(cond, __VA_ARGS__)
#define inform(...) do { std::printf(__VA_ARGS__); } while (0)

namespace gem5
{

class SimObject
{
  public:
    struct Params {
        std::string name = "sim_object";
    };

    SimObject() : _name("sim_object") {}
    explicit SimObject(const Params& p) : _name(p.name) {}
    virtual ~SimObject() = default;

    virtual void init() {}
    virtual void regStats() {}
    virtual void collateStats() {}
    virtual void resetStats() {}

    const std::string& name() const { return _name; }

  private:
    std::string _name;
};

} // namespace gem5

#endif // __PACE_COMPAT_SIM_OBJECT_HH__
