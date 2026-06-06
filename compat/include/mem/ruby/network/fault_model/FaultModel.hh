#ifndef __PACE_COMPAT_FAULT_MODEL_HH__
#define __PACE_COMPAT_FAULT_MODEL_HH__

#include <string>

namespace gem5
{
namespace ruby
{

static constexpr int BASELINE_TEMPERATURE_CELCIUS = 71;

class FaultModel
{
  public:
    int number_of_fault_types = 0;
    int declare_router(int, int, int, int, int) { return 0; }
    bool fault_vector(int, int, float*) { return false; }
    bool fault_prob(int, int, float*) { return false; }
    std::string fault_type_to_string(int) const { return ""; }
};

} // namespace ruby
} // namespace gem5

#endif // __PACE_COMPAT_FAULT_MODEL_HH__
