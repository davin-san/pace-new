#ifndef __PACE_COMPAT_PARAMS_BASIC_ROUTER_HH__
#define __PACE_COMPAT_PARAMS_BASIC_ROUTER_HH__

#include "sim/clocked_object.hh"

namespace gem5
{
namespace ruby
{

struct BasicRouterParams : public ClockedObject::Params
{
    uint32_t router_id = 0;
    uint32_t latency = 1;
};

} // namespace ruby
} // namespace gem5

#endif
