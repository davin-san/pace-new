#include "mem/ruby/network/BasicRouter.hh"

namespace gem5
{
namespace ruby
{

BasicRouter::BasicRouter(const Params& p)
    : ClockedObject(p), m_id(p.router_id), m_latency(p.latency)
{}

} // namespace ruby
} // namespace gem5
