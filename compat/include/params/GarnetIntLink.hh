#ifndef __PACE_COMPAT_PARAMS_GARNET_INT_LINK_HH__
#define __PACE_COMPAT_PARAMS_GARNET_INT_LINK_HH__

#include "params/BasicIntLink.hh"

namespace gem5
{
namespace ruby
{
namespace garnet
{

class NetworkLink;
class CreditLink;
class NetworkBridge;

struct GarnetIntLinkParams : public ruby::BasicIntLinkParams
{
    NetworkLink* network_link = nullptr;
    CreditLink* credit_link = nullptr;
    bool src_cdc = false;
    bool dst_cdc = false;
    bool src_serdes = false;
    bool dst_serdes = false;
    NetworkBridge* src_net_bridge = nullptr;
    NetworkBridge* dst_net_bridge = nullptr;
    NetworkBridge* src_cred_bridge = nullptr;
    NetworkBridge* dst_cred_bridge = nullptr;
};

} // namespace garnet
} // namespace ruby
} // namespace gem5

#endif
