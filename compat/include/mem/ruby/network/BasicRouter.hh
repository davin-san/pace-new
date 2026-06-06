#ifndef __PACE_COMPAT_BASIC_ROUTER_HH__
#define __PACE_COMPAT_BASIC_ROUTER_HH__

#include <iostream>

#include "params/BasicRouter.hh"
#include "sim/clocked_object.hh"

namespace gem5
{
namespace ruby
{

class BasicRouter : public ClockedObject
{
  public:
    typedef BasicRouterParams Params;
    explicit BasicRouter(const Params& p);

    void init() override {}
    void print(std::ostream& out) const { out << "[BasicRouter]"; }

  protected:
    uint32_t m_id;
    uint32_t m_latency;
};

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_BASIC_ROUTER_HH__
