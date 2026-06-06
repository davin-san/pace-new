#ifndef __PACE_COMPAT_BASE_TYPES_HH__
#define __PACE_COMPAT_BASE_TYPES_HH__

#include <cstdint>
#include <string>

namespace gem5
{

using Tick = uint64_t;
using Cycles = uint64_t;
using PortID = int;
using Addr = uint64_t;

struct Packet {};
struct WriteMask {};

Tick curTick();

} // namespace gem5

#endif // __PACE_COMPAT_BASE_TYPES_HH__
