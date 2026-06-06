#ifndef __PACE_COMPAT_PARAMS_GARNET_EXT_LINK_HH__
#define __PACE_COMPAT_PARAMS_GARNET_EXT_LINK_HH__

#include <vector>

#include "params/BasicExtLink.hh"

namespace gem5
{
namespace ruby
{
namespace garnet
{

class NetworkLink;
class CreditLink;
class NetworkBridge;

struct GarnetExtLinkParams : public ruby::BasicExtLinkParams
{
    std::vector<NetworkLink*> network_links = {nullptr, nullptr};
    std::vector<CreditLink*> credit_links = {nullptr, nullptr};
    bool ext_cdc = false;
    bool int_cdc = false;
    bool ext_serdes = false;
    bool int_serdes = false;
    std::vector<NetworkBridge*> ext_net_bridge = {nullptr, nullptr};
    std::vector<NetworkBridge*> int_net_bridge = {nullptr, nullptr};
    std::vector<NetworkBridge*> ext_cred_bridge = {nullptr, nullptr};
    std::vector<NetworkBridge*> int_cred_bridge = {nullptr, nullptr};
};

} // namespace garnet
} // namespace ruby
} // namespace gem5

#endif
