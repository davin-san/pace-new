#ifndef __PACE_COMPAT_PARAMS_BASIC_LINK_HH__
#define __PACE_COMPAT_PARAMS_BASIC_LINK_HH__

#include <vector>

#include "sim/sim_object.hh"

namespace gem5
{
namespace ruby
{

struct BasicLinkParams : public SimObject::Params
{
    Cycles latency = 1;
    int bandwidth_factor = 16;
    int weight = 1;
    std::vector<int> supported_vnets;
};

} // namespace ruby
} // namespace gem5

#endif
