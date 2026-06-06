#ifndef __PACE_COMPAT_NETDEST_HH__
#define __PACE_COMPAT_NETDEST_HH__

#include <algorithm>
#include <iostream>
#include <string>
#include <vector>

#include "base/types.hh"

namespace gem5
{
namespace ruby
{

using NodeID = int;
using SwitchID = int;
using PortDirection = std::string;

enum MachineType { MachineType_FIRST = 0, MachineType_NUM = 1 };

struct MachineID
{
    MachineType type;
    int num;
};

inline int MachineType_base_number(MachineType type)
{
    return type == MachineType_FIRST ? 0 : 1000000;
}

class NetDest
{
  public:
    NetDest() = default;
    explicit NetDest(void*) {}

    void add(NodeID id)
    {
        if (std::find(_dests.begin(), _dests.end(), id) == _dests.end()) {
            _dests.push_back(id);
        }
    }

    void add(MachineID id)
    {
        add(MachineType_base_number(id.type) + id.num);
    }

    void clear() { _dests.clear(); }
    std::vector<NodeID> getAllDest() const { return _dests; }

    bool intersectionIsNotEmpty(const NetDest& other) const
    {
        for (auto id : _dests) {
            if (std::find(other._dests.begin(), other._dests.end(), id) !=
                other._dests.end()) {
                return true;
            }
        }
        return false;
    }

    void removeNetDest(const NetDest& other)
    {
        for (auto id : other._dests) {
            _dests.erase(std::remove(_dests.begin(), _dests.end(), id),
                         _dests.end());
        }
    }

    void print() const
    {
        std::cout << "{";
        for (auto id : _dests) {
            std::cout << id << " ";
        }
        std::cout << "}";
    }

  private:
    std::vector<NodeID> _dests;
};

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_NETDEST_HH__
