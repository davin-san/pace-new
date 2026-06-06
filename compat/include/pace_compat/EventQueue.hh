#ifndef __PACE_COMPAT_EVENT_QUEUE_HH__
#define __PACE_COMPAT_EVENT_QUEUE_HH__

#include <algorithm>
#include <array>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

#include "pace_compat/Trace.hh"
#include "sim/clocked_object.hh"

namespace gem5
{

class EventQueue
{
  public:
    void schedule(ClockedObject* object, Tick when)
    {
        if (!scheduled(object, when)) {
            eventSlot(when).push_back(object);
            if (pace::traceEnabled()) {
                pace::traceEvent("event.schedule", {
                    {"when", pace::traceValue(when)},
                    {"target", pace::traceValue(object ? object->name() : "")},
                });
            }
        }
    }

    bool scheduled(ClockedObject* object, Tick when) const
    {
        if (isNear(when)) {
            const auto& bucket = _near_events[ringIndex(when)];
            if (bucket.tick == when &&
                contains(bucket.events, object)) {
                return true;
            }
        }

        auto it = _far_events.find(when);
        if (it != _far_events.end()) {
            return contains(it->second, object);
        }
        return false;
    }

    void setCurTick(Tick tick) { _cur_tick = tick; }
    Tick getCurTick() const { return _cur_tick; }

    void process()
    {
        while (true) {
            std::vector<ClockedObject*> slot = takeCurrentSlot();
            if (slot.empty()) {
                return;
            }
            if (slot.size() > 1) {
                std::stable_sort(slot.begin(), slot.end(),
                    [this](ClockedObject* lhs, ClockedObject* rhs) {
                        const ObjectMeta& lhs_meta = meta(lhs);
                        const ObjectMeta& rhs_meta = meta(rhs);
                        if (lhs_meta.priority != rhs_meta.priority) {
                            return lhs_meta.priority < rhs_meta.priority;
                        }
                        return lhs_meta.name < rhs_meta.name;
                    });
            }
            for (auto* object : slot) {
                if (pace::traceEnabled()) {
                    pace::traceEvent("event.wakeup", {
                        {"target",
                         pace::traceValue(object ? object->name() : "")},
                    });
                }
                object->wakeup();
            }
        }
    }

  private:
    static constexpr Tick near_window = 256;

    struct ObjectMeta {
        int priority = 0;
        std::string name;
    };

    struct EventBucket {
        Tick tick = static_cast<Tick>(-1);
        std::vector<ClockedObject*> events;
    };

    static bool contains(const std::vector<ClockedObject*>& slot,
                         ClockedObject* object)
    {
        return std::find(slot.begin(), slot.end(), object) != slot.end();
    }

    bool isNear(Tick when) const
    {
        return when >= _cur_tick && when < _cur_tick + near_window;
    }

    static size_t ringIndex(Tick when)
    {
        return static_cast<size_t>(when % near_window);
    }

    std::vector<ClockedObject*>& eventSlot(Tick when)
    {
        if (isNear(when)) {
            auto& bucket = _near_events[ringIndex(when)];
            if (bucket.tick != when) {
                bucket.tick = when;
                bucket.events.clear();
            }
            return bucket.events;
        }
        return _far_events[when];
    }

    std::vector<ClockedObject*> takeCurrentSlot()
    {
        std::vector<ClockedObject*> slot;
        auto& bucket = _near_events[ringIndex(_cur_tick)];
        if (bucket.tick == _cur_tick && !bucket.events.empty()) {
            slot = std::move(bucket.events);
            bucket.events.clear();
        }

        auto far = _far_events.find(_cur_tick);
        if (far != _far_events.end()) {
            if (slot.empty()) {
                slot = std::move(far->second);
            } else {
                auto far_slot = std::move(far->second);
                slot.insert(slot.end(), far_slot.begin(), far_slot.end());
            }
            _far_events.erase(far);
        }
        return slot;
    }

    const ObjectMeta& meta(ClockedObject* object)
    {
        auto it = _meta.find(object);
        if (it != _meta.end()) {
            return it->second;
        }

        ObjectMeta object_meta;
        object_meta.name = object ? object->name() : "";
        object_meta.priority = priority(object_meta.name);
        auto [inserted, _] = _meta.emplace(object, std::move(object_meta));
        return inserted->second;
    }

    static int priority(const std::string& name)
    {
        if (name.empty()) {
            return 0;
        }
        if (name.find("_net") != std::string::npos) {
            return 0;
        }
        if (name.find("router") != std::string::npos) {
            return 1;
        }
        if (name.find("network_interface") != std::string::npos) {
            return 2;
        }
        if (name.find("credit") != std::string::npos) {
            return 3;
        }
        return 2;
    }

    Tick _cur_tick = 0;
    std::array<EventBucket, near_window> _near_events;
    std::unordered_map<Tick, std::vector<ClockedObject*>> _far_events;
    std::unordered_map<ClockedObject*, ObjectMeta> _meta;
};

EventQueue& eventQueue();

} // namespace gem5

#endif // __PACE_COMPAT_EVENT_QUEUE_HH__
