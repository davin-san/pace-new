#ifndef __PACE_COMPAT_PARAMS_GARNET_NETWORK_HH__
#define __PACE_COMPAT_PARAMS_GARNET_NETWORK_HH__

#include <vector>

#include "mem/ruby/network/BasicRouter.hh"
#include "mem/ruby/network/Network.hh"
#include "mem/ruby/network/fault_model/FaultModel.hh"

namespace gem5
{
namespace ruby
{
namespace garnet
{

struct GarnetNetworkParams : public ruby::NetworkParams
{
    int num_rows = 0;
    uint32_t ni_flit_size = 16;
    uint32_t buffers_per_data_vc = 4;
    uint32_t buffers_per_ctrl_vc = 1;
    int routing_algorithm = 0;
    bool enable_fault_model = false;
    FaultModel* fault_model = nullptr;
    std::vector<BasicRouter*> routers;
    std::vector<ClockedObject*> netifs;
};

} // namespace garnet
} // namespace ruby
} // namespace gem5

#endif
