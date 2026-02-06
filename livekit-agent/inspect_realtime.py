
from livekit.plugins.google import realtime
import inspect

print("Methods of RealtimeModel:")
for name, method in inspect.getmembers(realtime.RealtimeModel):
    if not name.startswith('_'):
        print(name)

print("\nHelp on RealtimeModel:")
# print(help(realtime.RealtimeModel)) # Avoid help() paging
print(realtime.RealtimeModel.__doc__)
