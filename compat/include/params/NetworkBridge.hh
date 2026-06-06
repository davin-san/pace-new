#ifndef __PACE_COMPAT_PARAMS_NETWORK_BRIDGE_HH__
#define __PACE_COMPAT_PARAMS_NETWORK_BRIDGE_HH__

#include "params/CreditLink.hh"

namespace gem5
{
namespace ruby
{
namespace garnet
{

class NetworkLink;

namespace enums
{
enum CDCType { LINK_OBJECT = 0, OBJECT_LINK = 1 };
}

struct NetworkBridgeParams : public CreditLinkParams
{
    NetworkLink* link = nullptr;
    int vtype = enums::LINK_OBJECT;
    Cycles serdes_latency = 1;
    Cycles cdc_latency = 1;
};

} // namespace garnet
} // namespace ruby
} // namespace gem5

#endif
