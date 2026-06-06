#ifndef __PACE_COMPAT_RUBY_SYSTEM_HH__
#define __PACE_COMPAT_RUBY_SYSTEM_HH__

#include "base/types.hh"
#include "mem/ruby/common/NetDest.hh"

namespace gem5
{
namespace ruby
{

class RubySystem
{
  public:
    Cycles getStartCycle() const { return 0; }
    int MachineType_base_number(MachineType type) const
    {
        return gem5::ruby::MachineType_base_number(type);
    }
};

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_RUBY_SYSTEM_HH__
