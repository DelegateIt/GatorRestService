import gator.config as config

########################
# Handler Helper Class #
########################

class MigrationHandlers():
    def __init__(self, cur_version):
        self.handlers = {}
        self.cur_version = cur_version

    def add_handler(self, version, handler_cls):
        if self.handlers.get(version) is not None:
            raise ValueError("Handler for version %s already exists" % version)

        self.handlers[version] = handler_cls

    def migrate_forward_item(self, item):
        for version in range(int(item["version"]), self.cur_version):
            self.handlers[version].forward(item)

        return item.save()

    def migrate_backward_item(self, item):
        for version in range(self.cur_version, item["version"]):
            self.handlers[version].backward(item)

        return item.save()

####################
# General Handlers #
####################

class VersionHandler():
    @staticmethod
    def forward(item):
        item["version"] = 1

    @staticmethod
    def backward(item):
        item["version"] = 0
