#ifndef __PACE_COMPAT_PARAMS_GARNET_NETWORK_INTERFACE_HH__
#define __PACE_COMPAT_PARAMS_GARNET_NETWORK_INTERFACE_HH__

#include "sim/clocked_object.hh"

namespace gem5
{
namespace ruby
{
namespace garnet
{

struct GarnetNetworkInterfaceParams : public ClockedObject::Params
{
    int id = 0;
    int virt_nets = 3;
    int garnet_deadlock_threshold = 50000;
};

} // namespace garnet
} // namespace ruby
} // namespace gem5

#endif
