CXX      ?= g++
BUILD    ?= release

COMMON_CXXFLAGS = -std=c++17 -Wall -Wextra -Wno-unused-parameter

ifeq ($(BUILD),debug)
CXXFLAGS ?= $(COMMON_CXXFLAGS) -O0 -g
else ifeq ($(BUILD),trace)
CXXFLAGS ?= $(COMMON_CXXFLAGS) -O0 -g -DPACE_ENABLE_DPRINTF_TRACE
else ifeq ($(BUILD),profile)
CXXFLAGS ?= $(COMMON_CXXFLAGS) -O3 -g -DNDEBUG -fno-omit-frame-pointer
else
CXXFLAGS ?= $(COMMON_CXXFLAGS) -O3 -march=native -flto -DNDEBUG
endif

LDFLAGS ?=

SRCDIR    = src
COMPATDIR = compat
BUILDDIR  = build/$(BUILD)
TARGET    = pace-new

INCLUDES = -I$(COMPATDIR)/include -I.

GARNET_SRCS := $(wildcard $(SRCDIR)/*.cc)
COMPAT_SRCS := $(wildcard $(COMPATDIR)/src/*.cc)
SRCS := $(GARNET_SRCS) $(COMPAT_SRCS)
OBJS := $(patsubst %.cc,$(BUILDDIR)/%.o,$(SRCS))
DEPS := $(OBJS:.o=.d)

.PHONY: all clean identity release debug trace profile

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $^

$(BUILDDIR)/%.o: %.cc
	mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -MMD -MP -c -o $@ $<

identity:
	python3 tools/check_garnet_identity.py

release:
	$(MAKE) BUILD=release all

debug:
	$(MAKE) BUILD=debug all

trace:
	$(MAKE) BUILD=trace all

profile:
	$(MAKE) BUILD=profile all

clean:
	rm -rf $(BUILDDIR) $(TARGET)

-include $(DEPS)
