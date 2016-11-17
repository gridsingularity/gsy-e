from logging import LoggerAdapter


class TaggedLogWrapper(LoggerAdapter):
    def process(self, msg, kwargs):
        msg = "[{}] {}".format(self.extra, msg)
        return msg, kwargs
