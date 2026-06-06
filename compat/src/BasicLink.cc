#include "mem/ruby/network/BasicLink.hh"

namespace gem5
{
namespace ruby
{

BasicLink::BasicLink(const Params& p)
    : SimObject(p), m_latency(p.latency),
      m_bandwidth_factor(p.bandwidth_factor), m_weight(p.weight),
      mVnets(p.supported_vnets)
{}

} // namespace ruby
} // namespace gem5
