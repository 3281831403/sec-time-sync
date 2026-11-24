集群时间同步之后，跨闰秒那一刻的令牌校验集体失败，反而放行了一批未来时间戳：偏移采样不丢弃负延迟样本；偏移估计取全部样本的平均值而不是最小延迟子集的中位数；应用偏移时直接改墙钟，回拨未参考单调时钟；闰秒修正按固定偏移加一秒，插入秒被重复计数两次；闰秒表按年份匹配而不是按具体时刻匹配；单调性判定允许相等，重复时间戳被当成正常；未来时间戳窗口用无限大，未来值一律放行；未来时间戳判定用严格不等，恰好等于窗口上界的值被拒；配置校验不检查是否启用单调时钟；批量同步复用偏移值，第二台主机沿用第一台主机的偏移。engine/clock/sync.py 是核心，tests/clock/test_sync.py 15个红。要修的是：按上面的顺序把 10 个缺陷逐个修掉。

题目说明
这是一个安全缺陷修复题。集群在跨闰秒时同时出现墙钟回拨、闰秒重复计数和未来时间戳放行，令牌校验因此大面积误判。实现文件里的八个桩覆盖采样、估计、应用、闰秒修正、单调性、未来窗口、配置校验和批量同步。测试已经写成强约束，修复时不能降低断言强度。

字段表

运行方式
在仓库根目录执行：
python -m pytest tests -q

自检基线
预期结果必须恰好是 15 failed。十五个失败都应停在 engine/clock/sync.py 的 NotImplementedError，不能出现 collection error、import error、语法错误或断言先于桩调用发生。只允许使用标准库和 pytest。

tests 不可修改
tests/clock/test_sync.py 是验收基准，不得修改、弱化或删除。修复者只应编辑 engine/clock/sync.py，按题面顺序逐个实现八个桩。不要为了让测试变绿而改测试数据或断言。

engine 嵌套布局说明
engine 是仓库根目录下的顶层 Python 包，clock 是 engine 的子包，sync 是 clock 下唯一的实现模块。tests/clock 只承载测试，不是实现包。pytest 通过 python -m pytest 从仓库根目录启动，因此 engine.clock.sync 可以直接导入；不需要安装包，也不要把 sync.py 移到仓库根目录或另建一份实现。

核心契约
offset_sample 返回 offset 与 delay 两个整数键；delay 小于零时返回空字典，零延迟有效。
estimate_offset 在样本为空时返回零；否则按 delay 升序取前一半，再对这部分 offset 取中位数，偶数个取中间两数的整数平均。
apply_offset 先算墙钟加偏移；若结果早于原墙钟，判定为回拨，返回原墙钟与单调时钟读数中的较大者，绝不返回更早的墙钟值。
leap_second_adjust 的 ts 使用 YYYYMMDDHHMMSS 整数编码；leap_table 以具体闰秒时刻为键，值为该时刻的累计插入数。返回连续逻辑秒，闰秒标签独占一秒，既不与前一秒重复，也不跳过下一秒。
monotonic_ok 只在当前值严格大于前值时返回真；相等和回拨都返回假。
future_guard 使用闭区间，接受 now 减 window 到 now 加 window 之间的时间戳，含两个端点，窗口有限，更远的未来值拒绝。
validate_config 返回问题代码列表，代码为 max_offset_missing、leap_table_missing、monotonic_disabled；配置完整且启用单调时钟时返回空列表。
sync_batch 的 hosts 是包含 id 与 samples 的映射列表，返回 id 到估计偏移的映射；每台主机只使用自己的采样，批次之间不得共享偏移。

验收测试
test_offset_sample_discards_negative_delay
test_estimate_offset_uses_median_of_fastest_half
test_apply_offset_consults_monotonic_on_backward_wall
test_leap_second_adjust_does_not_double_count_inserted_second
test_leap_second_adjust_matches_exact_instant_not_year
test_monotonic_ok_rejects_equal_timestamps
test_future_guard_rejects_far_future_timestamp
test_future_guard_includes_window_upper_bound
test_validate_config_requires_monotonic_clock
test_sync_batch_uses_per_host_offset
test_estimate_offset_returns_zero_without_samples
test_offset_sample_symmetric_round_trip_gives_pure_offset
test_apply_offset_backward_is_detected_without_wall_mutation
test_leap_second_timestamp_is_not_repeated
test_sync_batch_independent_batches_match_individual_syncs

## 字段表

| 字段 | 取值 |
| --- | --- |
| 所属领域 | 安全 |
| 子方向 | 漏洞检测与攻防 |
| 任务类型 | Bugfix |
| 语言/框架 | Python 3, pytest |
| 环境可复现等级 | 无外部依赖 |

