#ifndef __PACE_COMPAT_PARAMS_NETWORK_LINK_HH__
#define __PACE_COMPAT_PARAMS_NETWORK_LINK_HH__

#include <vector>

#include "sim/clocked_object.hh"

namespace gem5
{
namespace ruby
{
namespace garnet
{

struct NetworkLinkParams : public ClockedObject::Params
{
    int link_id = 0;
    Cycles link_latency = 1;
    int vcs_per_vnet = 4;
    int virt_nets = 3;
    std::vector<int> supported_vnets;
    uint32_t width = 16;
};

} // namespace garnet
} // namespace ruby
} // namespace gem5

#endif
