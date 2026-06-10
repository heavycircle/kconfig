from pathlib import Path

from kconfig.core.config import state
from kconfig.core.parser import run_query
from kconfig.core.parser.declaration import parse_struct_specifier
from kconfig.styling_api import render_struct, ui


two = b"""
typedef struct cpumask { DECLARE_BITMAP(bits, NR_CPUS); } cpumask_t;
"""

code = b"""
struct rt_rq {
	struct rt_prio_array active;
	unsigned long rt_nr_running;
#if defined CONFIG_SMP || defined CONFIG_RT_GROUP_SCHED
	struct {
		int curr; /* highest queued rt task prio */
#if ! defined CONFIG_RT_GROUP_SCHED
        long next;
#elif defined CONFIG_SMP
		int next; /* next highest */
#endif
	} highest_prio;
#endif
};
"""

state.kernel_version = "3.2.63"
for _, captures in run_query("struct-list", code):
    if "struct.def" not in captures:
        continue

    node = captures["struct.def"][0]
    res = parse_struct_specifier(node, Path(__file__), True)
    ui.raw.print(render_struct(res))
