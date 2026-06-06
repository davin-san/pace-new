class BaseTopology:
    description = "BaseTopology"

    def makeTopology(self, options, network, IntLink, ExtLink, Router):
        raise NotImplementedError("BaseTopology must be overridden")

    def registerTopology(self, options):
        pass


class SimpleTopology(BaseTopology):
    description = "SimpleTopology"

    def __init__(self, controllers):
        self.nodes = controllers

    def addController(self, controller):
        self.nodes.append(controller)

    def __len__(self):
        return len(self.nodes)
