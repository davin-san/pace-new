#ifndef __PACE_COMPAT_PARAMS_NETWORK_HH__
#define __PACE_COMPAT_PARAMS_NETWORK_HH__

#include <string>
#include <vector>

#include "sim/clocked_object.hh"

namespace gem5
{
namespace ruby
{

class RubySystem;
class Topology;

struct NetworkParams : public ClockedObject::Params
{
    int number_of_virtual_networks = 3;
    int number_of_nodes = 0;
    std::vector<bool> vnet_ordered = {true, false, false};
    std::vector<std::string> vnet_type_names = {
        "request", "forward", "response"
    };
    Topology* topology = nullptr;
    RubySystem* ruby_system = nullptr;
};

} // namespace ruby
} // namespace gem5

#endif
