#ifndef __PACE_COMPAT_BASIC_LINK_HH__
#define __PACE_COMPAT_BASIC_LINK_HH__

#include <iostream>
#include <vector>

#include "params/BasicExtLink.hh"
#include "params/BasicIntLink.hh"
#include "params/BasicLink.hh"
#include "sim/sim_object.hh"

namespace gem5
{
namespace ruby
{

class BasicLink : public SimObject
{
  public:
    typedef BasicLinkParams Params;
    explicit BasicLink(const Params& p);

    void print(std::ostream& out) const { out << "[BasicLink]"; }

    Cycles m_latency;
    int m_bandwidth_factor;
    int m_weight;
    std::vector<int> mVnets;
};

class BasicExtLink : public BasicLink
{
  public:
    typedef BasicExtLinkParams Params;
    explicit BasicExtLink(const Params& p) : BasicLink(p) {}
};

class BasicIntLink : public BasicLink
{
  public:
    typedef BasicIntLinkParams Params;
    explicit BasicIntLink(const Params& p) : BasicLink(p) {}
};

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_BASIC_LINK_HH__
