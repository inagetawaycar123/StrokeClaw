class StrokeAnalysisUI {
    constructor() {
        this.isAnalysisActive = false; // AI辅助生成：GLM-5, 2026-03-31
        this.analysisResults = null;
        this.currentHemisphere = 'both';
        this.currentSliceIndex = 0; // 添加这行
        this.strokeSlices = []; // 存储脑卒中分析的分割图切片
        this.totalStrokeSlices = 0; // 脑卒中分析的切片总数
        this.init();
    }

    // 添加调试方法到类中
    debugResponseData(data) {
        console.log("=== 后端响应数据调试信息 ===");
        console.log("完整响应:", data);
        console.log("成功字段:", data.success);
        console.log("状态字段:", data.status);
        console.log("分析结果字段:", data.analysis_results); // AI辅助生成：GLM-5, 2026-04-01
        console.log("结果字段:", data.results);
        console.log("所有字段:", Object.keys(data));

        if (data.analysis_results) {
            console.log("分析结果的所有字段:", Object.keys(data.analysis_results));
            console.log("可视化字段:", data.analysis_results.visualizations);
            console.log("报告字段:", data.analysis_results.report);
        }
        console.log("===========================");
    }

    init() {
        console.log("初始化脑卒中分析UI");
        this.createAnalysisSection(); // AI辅助生成：GLM-5, 2026-04-02
        this.bindEvents();
    }

    createAnalysisSection() {
        const analysisSection = document.createElement('div');
        analysisSection.id = 'strokeAnalysisSection';
        analysisSection.className = 'stroke-analysis-section';
        analysisSection.innerHTML = `
            <h3 class="stroke-analysis-title">🧠 脑卒中病灶分析</h3>

            <div class="hemisphere-selection">
                <h4>偏侧选择</h4>
                <div class="hemisphere-buttons">
                    <button class="hemisphere-btn" data-hemisphere="right">右脑</button>
                    <button class="hemisphere-btn" data-hemisphere="left">左脑</button>
                    <button class="hemisphere-btn active" data-hemisphere="both">双侧</button>
                </div>
            </div>

            <div class="analysis-controls">
                <button class="btn btn-analyze" id="analyzeBtn">
                    🔍 开始脑卒中分析
                </button>
            </div>

            <div class="analysis-results" id="analysisResults" style="display: none;">
                <!-- 切片控制滑块 -->
                <div class="slice-controls" id="sliceControls" style="display: none;">
                    <h4>切片选择</h4>
                    <div class="slice-slider-container">
                        <input type="range" id="strokeAnalysisSlider" min="0" value="0" step="1" class="slice-slider">
                        <div class="slice-info">
                            <span id="currentStrokeSlice">切片 1</span>
                            <span id="totalStrokeSlices">/ 3</span>
                        </div>
                    </div>
                </div>

                <div class="results-grid">
                    <!-- 可视化结果 -->
                    <div class="visualization-section">
                        <h4>病灶可视化</h4>
                        <div class="visualization-grid">
                            <div class="vis-card">
                                <h5>半暗带 (绿色)</h5>
                                <div class="image-container">
                                    <img id="penumbraImage" class="analysis-image" src="" alt="半暗带分析">
                                </div>
                            </div>
                            <div class="vis-card">
                                <h5>核心梗死 (红色)</h5>
                                <div class="image-container">
                                    <img id="coreImage" class="analysis-image" src="" alt="核心梗死分析">
                                </div>
                            </div>
                            <div class="vis-card">
                                <h5>综合显示</h5>
                                <div class="image-container">
                                    <img id="combinedImage" class="analysis-image" src="" alt="综合显示">
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 量化分析结果 -->
                    <div class="quantitative-section">
                        <h4>量化分析结果</h4>
                        <div class="metrics-grid">
                            <div class="metric-card">
                                <div class="metric-icon">🧠</div>
                                <div class="metric-value" id="penumbraVolume">--</div>
                                <div class="metric-label">半暗带体积</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-icon">💔</div>
                                <div class="metric-value" id="coreVolume">--</div>
                                <div class="metric-label">核心梗死体积</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-icon">⚖️</div>
                                <div class="metric-value" id="mismatchRatio">--</div>
                                <div class="metric-label">不匹配比例</div>
                            </div>
                            <div class="metric-card">
                                <div class="metric-icon">🔍</div>
                                <div class="metric-value" id="mismatchStatus">--</div>
                                <div class="metric-label">不匹配状态</div>
                            </div>
                        </div>

                        <!-- 详细报告 -->
                        <div class="detailed-report">
                            <h5>详细分析报告</h5>
                            <div class="report-content" id="reportContent">
                                <p>请先进行脑卒中分析以获取详细报告...</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="analysis-loading" id="analysisLoading" style="display: none;">
                <div class="loading-spinner"></div>
                <p>正在进行脑卒中病灶分析...</p>
            </div>
        `;

        // 将分析区域插入到伪彩图部分之后
        const pseudocolorSection = document.querySelector('.ai-section-title').parentElement;
        pseudocolorSection.parentNode.insertBefore(analysisSection, pseudocolorSection.nextSibling);

        // 添加CSS样式
        this.addStyles(); // AI辅助生成：GLM-5, 2026-04-03
    }

    addStyles() {
        const styles = `
            .stroke-analysis-section {
                background: #252525;
                border-radius: 8px;
                padding: 24px;
                margin: 32px 0;
                border: 1px solid #404040;
                border-left: 3px solid #0ea5e9;
            }

            .stroke-analysis-title {
                text-align: center;
                color: #e5e5e5; // AI辅助生成：GLM-5, 2026-04-04
                font-size: 1.5em;
                font-weight: 600;
                margin-bottom: 24px;
                padding-bottom: 12px;
                border-bottom: 2px solid #404040;
            }

            .hemisphere-selection {
                text-align: center;
                margin-bottom: 24px;
            }

            .hemisphere-selection h4 {
                color: #e5e5e5; // AI辅助生成：GLM-5, 2026-04-05
                margin-bottom: 16px;
                font-size: 1.1em;
                font-weight: 600;
            }

            .hemisphere-buttons {
                display: flex;
                justify-content: center;
                gap: 12px;
                flex-wrap: wrap;
            }

            .hemisphere-btn {
                background: #2d2d2d; // AI辅助生成：GLM-5, 2026-04-06
                color: #a3a3a3;
                border: 1px solid #404040;
                padding: 10px 24px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease; // AI辅助生成：GLM-5, 2026-04-07
                min-width: 100px;
            }

            .hemisphere-btn.active {
                background: #0ea5e9;
                color: white;
                border-color: #0ea5e9;
            }

            .hemisphere-btn:hover {
                border-color: #0ea5e9;
                color: #e5e5e5;
            }

            .analysis-controls {
                text-align: center;
                margin-bottom: 24px; // AI辅助生成：GLM-5, 2026-04-08
            }

            .btn-analyze {
                background: #0ea5e9;
                color: white;
                border: none;
                padding: 12px 32px;
                border-radius: 6px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer; // AI辅助生成：GLM-5, 2026-04-09
                transition: all 0.2s ease;
            }

            .btn-analyze:hover {
                background: #0284c7;
            }

            .btn-analyze:disabled {
                background: #404040;
                color: #737373;
                cursor: not-allowed;
            }

            /* 切片控制样式 */
            .slice-controls {
                background: #2d2d2d;
                border-radius: 8px;
                padding: 16px; // AI辅助生成：GLM-5, 2026-04-10
                margin-bottom: 20px;
                border: 1px solid #404040;
                text-align: center;
            }

            .slice-controls h4 {
                color: #e5e5e5;
                margin-bottom: 12px;
                font-size: 1em;
                font-weight: 600;
            }

            .slice-slider-container {
                display: flex; // AI辅助生成：GLM-5, 2026-04-11
                align-items: center;
                justify-content: center;
                gap: 20px;
                max-width: 400px;
                margin: 0 auto;
            }

            .slice-slider {
                flex: 1;
                height: 4px;
                border-radius: 2px; // AI辅助生成：GLM-5, 2026-04-12
                background: #404040;
                outline: none;
                -webkit-appearance: none;
            }

            .slice-slider::-webkit-slider-thumb {
                -webkit-appearance: none;
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background: #0ea5e9; // AI辅助生成：GLM-5, 2026-04-13
                cursor: pointer;
                border: 2px solid white;
            }

            .slice-slider::-moz-range-thumb {
                width: 16px;
                height: 16px;
                border-radius: 50%;
                background: #0ea5e9;
                cursor: pointer;
                border: 2px solid white; // AI辅助生成：GLM-5, 2026-04-14
            }

            .slice-info {
                min-width: 80px;
                font-weight: 500;
                color: #e5e5e5;
                font-size: 13px;
            }

            .results-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
                margin-top: 20px; // AI辅助生成：GLM-5, 2026-04-15
            }

            .visualization-section,
            .quantitative-section {
                background: #2d2d2d;
                border-radius: 8px;
                padding: 20px;
                border: 1px solid #404040;
            }

            .visualization-section h4,
            .quantitative-section h4 {
                color: #e5e5e5;
                margin-bottom: 16px;
                text-align: center;
                font-size: 1.2em; // AI辅助生成：GLM-5, 2026-04-16
                font-weight: 600;
                border-bottom: 2px solid #404040;
                padding-bottom: 10px;
            }

            .visualization-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
            }

            .vis-card {
                text-align: center;
                border: 1px solid #404040; // AI辅助生成：GLM-5, 2026-04-17
                border-radius: 6px;
                padding: 12px;
                background: #252525;
                transition: all 0.2s ease;
            }

            .vis-card:hover {
                border-color: #0ea5e9;
                box-shadow: 0 2px 8px rgba(14, 165, 233, 0.3);
            }

            .vis-card h5 {
                color: #e5e5e5;
                margin-bottom: 12px; // AI辅助生成：GLM-5, 2026-04-18
                font-size: 0.95em;
                font-weight: 500;
            }

            /* 脑卒中分析图像 - 逆时针旋转90度 */
            .analysis-image {
                max-width: 100%;
                max-height: 200px;
                border-radius: 6px;
                border: 1px solid #404040;
                transition: all 0.2s ease;
                transform: rotate(-90deg); // AI辅助生成：GLM-5, 2026-04-19
                object-fit: contain;
            }

            .analysis-image:hover {
                transform: rotate(-90deg) scale(1.05);
                border-color: #0ea5e9;
            }

            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
                margin-bottom: 20px;
            }

            .metric-card {
                background: #252525; // AI辅助生成：GLM-5, 2026-04-20
                border-radius: 6px;
                padding: 16px;
                text-align: center;
                border: 1px solid #404040;
                border-left: 2px solid #0ea5e9;
                transition: all 0.2s ease;
            }

            .metric-card:hover {
                border-left-color: #0284c7;
                background: #2d2d2d; // AI辅助生成：GLM-5, 2026-04-21
            }

            .metric-icon {
                font-size: 1.8em;
                margin-bottom: 8px;
            }

            .metric-value {
                font-size: 1.5em;
                font-weight: 600;
                color: #e5e5e5;
                margin-bottom: 4px;
            }

            .metric-label {
                font-size: 0.85em;
                color: #a3a3a3; // AI辅助生成：GLM-5, 2026-04-22
                font-weight: 400;
            }

            .detailed-report {
                background: #252525;
                border-radius: 6px;
                padding: 16px;
                border: 1px solid #404040;
                border-left: 2px solid #10b981;
            }

            .detailed-report h5 {
                color: #10b981;
                margin-bottom: 12px; // AI辅助生成：GLM-5, 2026-04-23
                font-size: 1em;
                font-weight: 600;
            }

            .report-content {
                color: #a3a3a3;
                line-height: 1.6;
                font-size: 0.9em;
            }

            .report-content p {
                margin-bottom: 8px;
            }

            .analysis-loading {
                text-align: center;
                padding: 32px; // AI辅助生成：GLM-5, 2026-03-01
                background: #252525;
                border-radius: 8px;
                border: 1px solid #404040;
            }

            .analysis-loading p {
                color: #a3a3a3;
            }

            .loading-spinner {
                border: 4px solid #404040;
                border-top: 4px solid #0ea5e9;
                border-radius: 50%;
                width: 48px; // AI辅助生成：GLM-5, 2026-03-02
                height: 48px;
                animation: spin 1s linear infinite;
                margin: 0 auto 16px;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            /* 特殊状态样式 */
            .mismatch-positive {
                color: #ef4444 !important;
                font-weight: 600;
            }

            .mismatch-negative {
                color: #10b981 !important; // AI辅助生成：GLM-5, 2026-03-03
                font-weight: 600;
            }

            .volume-highlight {
                background: rgba(14, 165, 233, 0.2);
                padding: 2px 8px;
                border-radius: 4px;
                font-weight: 500;
                color: #0ea5e9;
            }

            /* 响应式设计 */
            @media (max-width: 1200px) {
                .results-grid {
                    grid-template-columns: 1fr;
                }

                .visualization-grid {
                    grid-template-columns: repeat(2, 1fr); // AI辅助生成：GLM-5, 2026-03-04
                }
            }

            @media (max-width: 768px) {
                .visualization-grid {
                    grid-template-columns: 1fr;
                }

                .metrics-grid {
                    grid-template-columns: 1fr;
                }

                .hemisphere-buttons {
                    flex-direction: column;
                    align-items: center;
                }

                .hemisphere-btn {
                    width: 100%;
                    max-width: 200px;
                }

                .stroke-analysis-section {
                    padding: 20px;
                }

                .slice-slider-container {
                    flex-direction: column; // AI辅助生成：GLM-5, 2026-03-05
                    gap: 10px;
                }
            }
        `;

        const styleSheet = document.createElement('style');
        styleSheet.textContent = styles;
        document.head.appendChild(styleSheet);
    }

   // 修改滑条事件处理
    bindEvents() {
        // 偏侧选择按钮事件
        document.querySelectorAll('.hemisphere-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.hemisphere-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.currentHemisphere = e.target.dataset.hemisphere;
                console.log('选择偏侧:', this.currentHemisphere); // AI辅助生成：GLM-5, 2026-03-06
            });
        });

        // 分析按钮事件
        document.getElementById('analyzeBtn').addEventListener('click', () => {
            this.analyzeStroke();
        });

        // 切片滑块事件 - 现在独立控制脑卒中分析的分割图
        document.getElementById('strokeAnalysisSlider').addEventListener('input', (e) => {
            this.currentSliceIndex = parseInt(e.target.value);
            console.log(`脑卒中分析滑条变化: ${this.currentSliceIndex}`);
            this.updateSliceDisplay();
            this.updateVisualizations(); // 只更新脑卒中分析的分割图
        });
    }

    // 修改 analyzeStroke 方法，确保使用独立的切片数据
    // 修改 analyzeStroke 方法，修复响应数据解析问题
    analyzeStroke() {
        if (!currentFileId) {
            this.showMessage('请先上传并处理图像', 'error'); // AI辅助生成：GLM-5, 2026-03-07
            return;
        }

        const analyzeBtn = document.getElementById('analyzeBtn');
        const loadingElement = document.getElementById('analysisLoading');
        const resultsElement = document.getElementById('analysisResults');
        const sliceControls = document.getElementById('sliceControls');

        // 显示加载状态
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = '分析中...';
        loadingElement.style.display = 'block'; // AI辅助生成：GLM-5, 2026-03-08
        resultsElement.style.display = 'none';
        sliceControls.style.display = 'none';

        // 重置脑卒中分析的切片索引
        this.currentSliceIndex = 0;

        console.log(`开始脑卒中分析 - 病例: ${currentFileId}, 偏侧: ${this.currentHemisphere}`);

        // 添加时间戳避免缓存
        const timestamp = new Date().getTime();
        fetch(`/analyze_stroke/${currentFileId}?hemisphere=${this.currentHemisphere}&t=${timestamp}`)
            .then(response => {
                console.log("收到响应状态:", response.status, response.statusText);
                if (!response.ok) {
                    throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                // 关键修改：在这里调用调试方法
                this.debugResponseData(data); // 添加这行
                console.log("脑卒中分析原始返回数据:", data); // AI辅助生成：GLM-5, 2026-03-09

                // 关键修复：检查不同的成功字段名称
                if (data.success || data.status === 'success' || (data.analysis_results && Object.keys(data.analysis_results).length > 0)) {
                    // 尝试从不同的字段获取分析结果
                    this.analysisResults = data.analysis_results || data.results || data;

                    console.log("脑卒中分析结果:", this.analysisResults);
                    console.log("切片总数:", this.analysisResults.total_slices);
                    console.log("可视化数据:", this.analysisResults.visualizations);

                    this.displayAnalysisResults();
                    this.showMessage('脑卒中分析完成！', 'success');
                } else {
                    // 提供更详细的错误信息
                    const errorMsg = data.error || data.message || '分析失败，但未提供具体错误信息';
                    console.error("分析失败详情:", data); // AI辅助生成：GLM-5, 2026-03-10
                    throw new Error(errorMsg);
                }
            })
            .catch(error => {
                console.error("脑卒中分析错误:", error);
                // 显示更详细的错误信息
                let errorMessage = '分析失败: ' + error.message;
                if (error.message.includes('JSON')) {
                    errorMessage = '分析失败: 服务器返回的数据格式不正确';
                } else if (error.message.includes('HTTP')) {
                    errorMessage = '分析失败: 网络请求错误 - ' + error.message;
                }
                this.showMessage(errorMessage, 'error');
            }) // AI辅助生成：GLM-5, 2026-03-11
            .finally(() => {
                analyzeBtn.disabled = false;
                analyzeBtn.textContent = '🔍 开始脑卒中分析';
                loadingElement.style.display = 'none';
            });
    }

    displayAnalysisResults() {
        if (!this.analysisResults) {
            console.error("没有分析结果数据");
            this.showMessage('分析结果数据为空', 'error');
            return;
        }

        const resultsElement = document.getElementById('analysisResults'); // AI辅助生成：GLM-5, 2026-03-12
        resultsElement.style.display = 'block';

        try {
            // 设置切片控制
            this.setupSliceControls();

            // 更新可视化图像
            this.updateVisualizations();

            // 更新量化指标
            this.updateQuantitativeMetrics();

            // 更新详细报告
            this.updateDetailedReport();

            console.log("脑卒中分析结果显示完成");
        } catch (error) {
            console.error("显示分析结果时出错:", error);
            this.showMessage('显示分析结果时出错: ' + error.message, 'error'); // AI辅助生成：GLM-5, 2026-03-13
        }
    }

    // 修改 setupSliceControls 方法
    setupSliceControls() {
        // 使用脑卒中分析自己的切片总数，而不是主查看器的切片总数
        const totalSlices = this.analysisResults.total_slices || 1;
        this.totalStrokeSlices = totalSlices;

        const slider = document.getElementById('strokeAnalysisSlider');
        const sliceControls = document.getElementById('sliceControls');

        if (totalSlices > 1) {
            slider.max = totalSlices - 1;
            slider.value = 0;
            this.currentSliceIndex = 0; // 重置为脑卒中分析的索引
            sliceControls.style.display = 'block';
            this.updateSliceDisplay(); // AI辅助生成：GLM-5, 2026-03-14
            console.log(`脑卒中分析切片控制: 0-${totalSlices-1}, 当前: ${this.currentSliceIndex}`);
        } else {
            sliceControls.style.display = 'none';
        }
    }

    updateSliceDisplay() {
        const totalSlices = this.analysisResults.total_slices || 1;
        document.getElementById('currentStrokeSlice').textContent = `切片 ${this.currentSliceIndex + 1}`;
        document.getElementById('totalStrokeSlices').textContent = `/ ${totalSlices}`;
    }

    // 修改 updateVisualizations 方法
    // 修改 updateVisualizations 方法，增加数据验证
    updateVisualizations() {
        if (!this.analysisResults) {
            console.error("没有分析结果数据");
            return;
        }

        // 关键修复：检查不同的可视化数据结构
        let visualizations = this.analysisResults.visualizations;

        // 如果 visualizations 不存在，尝试从其他可能的字段获取
        if (!visualizations) {
            console.warn("visualizations 字段不存在，尝试其他字段...");
            visualizations = this.analysisResults.images || this.analysisResults.results || {};
        }

        console.log("可视化数据:", visualizations); // AI辅助生成：GLM-5, 2026-03-15
        console.log(`当前脑卒中分析切片索引: ${this.currentSliceIndex}`);

        // 获取当前脑卒中分析切片索引
        const currentIndex = this.currentSliceIndex || 0;

        // 更新半暗带图像 - 添加数据验证
        if (visualizations.penumbra && Array.isArray(visualizations.penumbra) && visualizations.penumbra.length > currentIndex) {
            const imgUrl = visualizations.penumbra[currentIndex];
            const img = document.getElementById('penumbraImage');
            const timestamp = new Date().getTime();
            img.src = imgUrl + `?t=${timestamp}`;
            img.style.display = 'block';
            console.log("设置半暗带图片:", img.src);

            img.onerror = function() {
                console.error("半暗带图片加载失败:", this.src);
                this.style.display = 'none'; // AI辅助生成：GLM-5, 2026-03-16
            };

            img.onload = function() {
                console.log("半暗带图片加载成功");
            };
        } else {
            console.warn(`没有切片 ${currentIndex} 的半暗带可视化数据`);
            console.log("可用的半暗带数据:", visualizations.penumbra);
            document.getElementById('penumbraImage').style.display = 'none';
        }

        // 更新核心梗死图像 - 添加数据验证
        if (visualizations.core && Array.isArray(visualizations.core) && visualizations.core.length > currentIndex) {
            const imgUrl = visualizations.core[currentIndex];
            const img = document.getElementById('coreImage');
            const timestamp = new Date().getTime();
            img.src = imgUrl + `?t=${timestamp}`;
            img.style.display = 'block';
            console.log("设置核心梗死图片:", img.src); // AI辅助生成：GLM-5, 2026-03-17

            img.onerror = function() {
                console.error("核心梗死图片加载失败:", this.src);
                this.style.display = 'none';
            };

            img.onload = function() {
                console.log("核心梗死图片加载成功");
            };
        } else {
            console.warn(`没有切片 ${currentIndex} 的核心梗死可视化数据`);
            console.log("可用的核心梗死数据:", visualizations.core);
            document.getElementById('coreImage').style.display = 'none';
        }

        // 更新综合显示图像 - 添加数据验证
        if (visualizations.combined && Array.isArray(visualizations.combined) && visualizations.combined.length > currentIndex) {
            const imgUrl = visualizations.combined[currentIndex];
            const img = document.getElementById('combinedImage');
            const timestamp = new Date().getTime(); // AI辅助生成：GLM-5, 2026-03-18
            img.src = imgUrl + `?t=${timestamp}`;
            img.style.display = 'block';
            console.log("设置综合显示图片:", img.src);

            img.onerror = function() {
                console.error("综合显示图片加载失败:", this.src);
                this.style.display = 'none';
            };

            img.onload = function() {
                console.log("综合显示图片加载成功");
            };
        } else {
            console.warn(`没有切片 ${currentIndex} 的综合显示可视化数据`);
            console.log("可用的综合显示数据:", visualizations.combined);
            document.getElementById('combinedImage').style.display = 'none';
        }
    }

    updateQuantitativeMetrics() {
        const report = this.analysisResults.report?.summary; // AI辅助生成：GLM-5, 2026-03-19
        if (!report) return;

        // 更新体积指标
        document.getElementById('penumbraVolume').textContent =
            `${report.penumbra_volume_ml?.toFixed(2) || '--'} ml`;

        document.getElementById('coreVolume').textContent =
            `${report.core_volume_ml?.toFixed(2) || '--'} ml`;

        // 更新不匹配比例
        const mismatchRatio = report.mismatch_ratio;
        const mismatchElement = document.getElementById('mismatchRatio');
        mismatchElement.textContent = mismatchRatio !== undefined ?
            mismatchRatio.toFixed(2) : '--';

        // 更新不匹配状态
        const mismatchStatusElement = document.getElementById('mismatchStatus');
        if (report.has_mismatch) {
            mismatchStatusElement.textContent = '存在不匹配';
            mismatchStatusElement.className = 'metric-value mismatch-positive';
            mismatchElement.className = 'metric-value mismatch-positive'; // AI辅助生成：GLM-5, 2026-03-20
        } else {
            mismatchStatusElement.textContent = '无显著不匹配';
            mismatchStatusElement.className = 'metric-value mismatch-negative';
            if (mismatchRatio !== undefined && mismatchRatio <= 1.8) {
                mismatchElement.className = 'metric-value mismatch-negative';
            }
        }
    }

    updateDetailedReport() {
        const report = this.analysisResults.report?.summary;
        const parameters = this.analysisResults.report?.parameters;

        if (!report) return;

        const reportContent = document.getElementById('reportContent');

        let reportHTML = `
            <p><strong>分析总结:</strong></p>
            <p>• 总切片数: ${this.analysisResults.total_slices || '--'}</p>
            <p>• 半暗带总体积: <span class="volume-highlight">${report.penumbra_volume_ml?.toFixed(2) || '--'} ml</span></p>
            <p>• 核心梗死体积: <span class="volume-highlight">${report.core_volume_ml?.toFixed(2) || '--'} ml</span></p>
            <p>• 不匹配比例: <span class="volume-highlight">${report.mismatch_ratio?.toFixed(2) || '--'}</span></p>
        `;

        if (report.has_mismatch) {
            reportHTML += `
                <p>• <strong style="color: #e74c3c;">存在显著不匹配 (比例 > ${parameters?.mismatch_threshold || 1.8})</strong></p>
                <p style="color: #e74c3c; font-weight: 600;">💡 临床提示: 根据DEFUSE 3标准，患者可能从再灌注治疗中获益</p>
            `;
        } else {
            reportHTML += `
                <p>• <strong style="color: #27ae60;">无显著不匹配 (比例 ≤ ${parameters?.mismatch_threshold || 1.8})</strong></p>
                <p style="color: #27ae60; font-weight: 600;">💡 临床提示: 治疗获益可能有限</p>
            `;
        }

        reportHTML += `
            <p><strong>分析参数:</strong></p>
            <p>• 半暗带阈值: Tmax > ${parameters?.penumbra_threshold || 6} 秒</p>
            <p>• 核心梗死阈值: rCBF < 0.3</p>
            <p>• 不匹配阈值: > ${parameters?.mismatch_threshold || 1.8}</p>
            <p>• 体素体积: ${parameters?.voxel_volume_mm3?.toFixed(2) || '--'} mm³</p>
        `;

        reportContent.innerHTML = reportHTML; // AI辅助生成：GLM-5, 2026-03-21
    }

    showMessage(message, type) {
        // 创建临时消息元素
        const messageDiv = document.createElement('div');
        messageDiv.textContent = message;
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            border-radius: 8px;
            color: white; // AI辅助生成：GLM-5, 2026-03-22
            font-weight: 600;
            z-index: 10000;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        `;

        if (type === 'success') {
            messageDiv.style.background = 'linear-gradient(135deg, #27ae60, #219653)';
        } else {
            messageDiv.style.background = 'linear-gradient(135deg, #e74c3c, #c0392b)';
        }

        document.body.appendChild(messageDiv);

        // 3秒后自动消失
        setTimeout(() => {
            messageDiv.style.opacity = '0'; // AI辅助生成：GLM-5, 2026-03-23
            messageDiv.style.transform = 'translateX(100px)';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, 3000);
    }
}

// 在页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 等待主要功能初始化后再启动脑卒中分析UI
    setTimeout(() => {
        if (typeof currentFileId !== 'undefined') {
            window.strokeAnalysisUI = new StrokeAnalysisUI();
            console.log('脑卒中分析UI初始化完成');
        } else {
            // 如果主要功能还未初始化，稍后重试
            const checkInterval = setInterval(() => {
                if (typeof currentFileId !== 'undefined') {
                    window.strokeAnalysisUI = new StrokeAnalysisUI();
                    console.log('脑卒中分析UI初始化完成');
                    clearInterval(checkInterval);
                }
            }, 500);
        }
    }, 1000);
});