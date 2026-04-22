# 项目实验报告：Phase 1 与 Phase 2A 对比

## 1. 实验目的

本实验用于评估金融研报问答系统在两种架构配置下的表现差异：

- **Phase 1（Baseline）**：`Fixed-256` 分块，不启用 RAPTOR。
- **Phase 2A（Advanced）**：`Semantic Chunking + RAPTOR`。

核心目标是验证高级架构是否在检索质量与回答质量上优于基线方案，并为后续架构调优提供依据。

---

## 2. 实验设置

根据 `docs/05_progress_report_guide.md`，两组实验遵循同一评估流程，仅修改架构变量。

### 2.1 配置对比

| 维度 | Phase 1 | Phase 2A |
| :-- | :-- | :-- |
| Chunking | `fixed` (`chunk_size=256`) | `semantic` |
| RAPTOR | `false` | `true` |
| 存储目录 | `./chroma_db/phase1_baseline` | `./chroma_db/phase2_raptor` |
| 评估脚本 | `src/evaluation/ragas_eval.py` | `src/evaluation/ragas_eval.py` |
| 输出文件 | `data/phase1_evaluation_report.csv` | `data/phase2_evaluation_report.csv` |

### 2.2 评估指标

采用 RAGAS 三个核心指标（`docs/02_evaluation_metrics.md`）：

1. **Context Precision**：检索上下文的精确命中能力。
2. **Faithfulness**：回答对检索内容的忠实程度（低幻觉）。
3. **Answer Relevancy**：回答对用户问题的直接相关性。

### 2.3 截图展示位（请在提交前替换）

> 说明：以下为报告截图占位符，提交前请替换为真实图片路径或直接粘贴图片。

#### S0 环境核查截图

![S0-环境核查截图（占位）](./images/S0_env_check.png)

**建议内容**：工作目录、`data/` 文件列表、配置摘要输出。

#### P1-1 Phase 1 配置截图

![P1-1-Phase1配置截图（占位）](./images/P1-1_phase1_config.png)

**建议内容**：`chunking`、`raptor`、`storage.chroma_persist_dir`、`evaluation.judge_model`。

#### P1-2 Phase 1 索引构建日志截图

![P1-2-Phase1索引日志截图（占位）](./images/P1-2_phase1_index_log.png)

#### P1-3 Phase 1 评估日志截图

![P1-3-Phase1评估日志截图（占位）](./images/P1-3_phase1_eval_log.png)

#### P2-1 Phase 2A 配置截图

![P2-1-Phase2A配置截图（占位）](./images/P2-1_phase2a_config.png)

#### P2-2 Phase 2A 索引构建日志截图

![P2-2-Phase2A索引日志截图（占位）](./images/P2-2_phase2a_index_log.png)

#### P2-3 Phase 2A 性能开销截图（可选）

![P2-3-Phase2A性能开销截图（占位）](./images/P2-3_phase2a_perf.png)

#### P2-4 Phase 2A 评估日志截图

![P2-4-Phase2A评估日志截图（占位）](./images/P2-4_phase2a_eval_log.png)

---

## 3. 实验数据说明

- 数据来源：`data/phase1_evaluation_report.csv` 与 `data/phase2_evaluation_report.csv`。
- 当前两份结果文件均为 **10 条样本**。
- 规范建议正式报告使用 **20 题标准测试集**，因此本报告结论属于阶段性结论，后续需在 20 题下复现实验。

---

## 4. 量化结果对比

### 4.1 指标均值对比

| 指标 | Phase 1 | Phase 2A | 变化量（P2A-P1） | 相对变化 |
| :-- | --: | --: | --: | --: |
| Context Precision | 0.6628 | 0.5527 | -0.1101 | -16.61% |
| Faithfulness | 0.9306 | 0.9448 | +0.0142 | +1.53% |
| Answer Relevancy | 0.8407 | 0.7686 | -0.0721 | -8.58% |
| 三指标综合均值 | 0.8014 | 0.7553 | -0.0461 | -5.75% |

### 4.2 样本层面观察

- **Context Precision**：10 题中 4 题提升、6 题下降，整体下降明显。
- **Faithfulness**：3 题提升、1 题下降、其余持平，整体小幅改善。
- **Answer Relevancy**：6 题提升、4 题下降，但存在个别大幅下滑样本，拉低总均值。

---

## 5. 结果分析

### 5.1 总体结论

在当前样本下，Phase 2A 未超过 Phase 1 的综合效果。  
表现特征为：**忠实度提升，但检索精度与回答相关性下滑**。

### 5.2 典型现象

1. **核心问题类查询出现检索偏移**
   - “本次研报的核心研究问题是什么？”在 Phase 2A 中上下文精度显著下降，回答更偏宏观描述，未直接锚定问题核心句。

2. **风险提示类问题出现异常样本**
   - “本报告中提到的主要风险提示有哪些？”在 Phase 2A 中 `answer_relevancy=0`，且 `faithfulness` 同步下降，为本轮最需优先排查的异常。

3. **部分推理类题目有改善**
   - 在“长期通胀预期变化”等问题上，Phase 2A 的检索精度明显提升，说明语义分块对部分语义关联问题有效。

---

## 6. 原因推断

结合实验输出，当前问题更可能来自“参数与链路调优不足”，而非高级架构无效：

- 语义分块与 RAPTOR 引入后，候选上下文空间变大，但重排与过滤策略不足，导致噪声块进入前列。
- 对事实定位类问题，语义召回链路不一定优于固定小块 + 强关键词定位。
- 样本量较小（10 题）导致均值对异常题敏感，需扩大样本验证稳定性。

---

## 7. 改进方案（下一轮实验）

1. **优先优化检索链路**
   - 加强 rerank 约束，降低低相关摘要块权重。
   - 在入库或召回阶段过滤目录、免责声明、页眉页脚等噪声文本。
   - 试行“题型分路”：事实题走短块精确召回，总结题走 RAPTOR。

2. **完善评估设置**
   - 按规范补齐到 20 题标准集，保证结论可比性与稳定性。
   - 除总体均值外，按题型分别统计（事实、推理、总结、结构化输出）。
   - 对异常样本建立逐题误差分析表，记录检索片段与最终回答偏差。

3. **补充中期报告素材**
   - 增加同题在 Phase 1/Phase 2A 的检索上下文对比截图。
   - 记录构建耗时、存储占用、CPU/内存峰值，形成“效果-开销”权衡分析。

---

## 8. 结论

本轮对比显示：

- **Phase 2A 在降低幻觉方面有正向收益**（Faithfulness 小幅提升）。
- **但在检索精度与问题命中度方面存在退化**（Context Precision 与 Answer Relevancy 下降）。
- 在未完成更充分调优前，系统整体效果仍以 Phase 1 更稳健。

因此，后续应以“检索质量校准 + 题型分路 + 20 题复现实验”为主线，验证 Phase 2A 在更完整设置下的真实收益。

---

## 9. 截图索引表（便于快速核对）

| 截图编号 | 对应位置 | 是否必需 | 建议文件名 |
| :-- | :-- | :-- | :-- |
| S0 | 环境准备与核查 | 必需 | `S0_env_check.png` |
| P1-1 | Phase 1 配置 | 必需 | `P1-1_phase1_config.png` |
| P1-2 | Phase 1 索引日志 | 必需 | `P1-2_phase1_index_log.png` |
| P1-3 | Phase 1 评估日志 | 必需 | `P1-3_phase1_eval_log.png` |
| P2-1 | Phase 2A 配置 | 必需 | `P2-1_phase2a_config.png` |
| P2-2 | Phase 2A 索引日志 | 必需 | `P2-2_phase2a_index_log.png` |
| P2-3 | Phase 2A 性能开销 | 可选（建议） | `P2-3_phase2a_perf.png` |
| P2-4 | Phase 2A 评估日志 | 必需 | `P2-4_phase2a_eval_log.png` |

