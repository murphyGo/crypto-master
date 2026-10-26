# CPU metric interpretation

Checked 2026-10-27 KST against [Fly's metric definitions](https://docs.fly.io/monitoring/metrics)
and [CPU quota documentation](https://docs.fly.io/machines/cpu-performance).
`fly_instance_cpu_balance` is a burst-balance gauge in centiseconds;
`fly_instance_cpu_throttle` is a cumulative counter in centiseconds;
`fly_instance_cpu_baseline` is measured in CPUs. The documented shared-vCPU
baseline is currently 5 ms per 80 ms period (6.25%), with burst allowance.

Preserve raw values. A positive, flat throttle counter does not by itself prove
new throttling during a selected observation window. Check consecutive increases,
counter decreases/resets and intervals crossing the boundary separately.
Fifteen-second samples cannot locate exact quota exhaustion or associate it
with one page request. The v66 counter rose from zero during its failed period;
the separate v67 interim capture has a zero counter throughout its captured
portion. Final original-window coverage is assessed on the later final capture.

Current guest capacity, accumulated balance, input generations and engine work
can vary between observations. Local paired source benchmarks establish the
removed CPU cost under controlled inputs; uncontrolled production windows do
not establish the same percentage improvement or a sole request-level cause.
Passing a window with positive balance does not qualify the original depleted,
cold, native or 1024 MiB conditions.
