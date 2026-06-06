#ifndef __PACE_COMPAT_PARAMS_GARNET_ROUTER_HH__
#define __PACE_COMPAT_PARAMS_GARNET_ROUTER_HH__

#include "params/BasicRouter.hh"

namespace gem5
{
namespace ruby
{
namespace garnet
{

struct GarnetRouterParams : public ruby::BasicRouterParams
{
    uint32_t virt_nets = 3;
    uint32_t vcs_per_vnet = 4;
    uint32_t width = 16;
};

} // namespace garnet
} // namespace ruby
} // namespace gem5

#endif
