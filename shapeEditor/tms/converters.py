class VersionConverter:
    regex = "[0-9.]+"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value

# class VersionConverter:
#     regex = "[0-9.]+"
#
#     def to_python(self, value):
#         return int(value)
#
#     def to_url(self, value):
#         return str(value)
