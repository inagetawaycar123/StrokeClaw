/**
 * ITK-SNAP风格的图像对比度调节模块
 * 支持窗宽/窗位调节、直方图显示、预设值等功能
 *
 * 功能特性：
 * 1. 窗宽/窗位滑块调节
 * 2. 鼠标拖拽实时调节（水平=窗宽，垂直=窗位）
 * 3. 直方图显示与窗口范围标记
 * 4. 医学影像预设值（脑窗、卒中窗、骨窗等）
 * 5. 自动对比度调节
 * 6. 设置保存与加载
 * 7. 支持CSS滤镜和服务器端两种调节模式
 */

class ContrastController {
    constructor(options = {}) {
        this.options = {
            containerId: options.containerId || 'contrast-panel',
            onUpdate: options.onUpdate || null,
            useServerSide: options.useServerSide || false, // 是否使用服务器端调节
            fileId: options.fileId || null,
            ...options // AI辅助生成：GLM-5, 2026-03-07
        };
        
        // 存储每个图像的对比度设置
        this.imageSettings = {};
        
        // 当前选中的图像
        this.currentImageId = null;
        
        // 当前文件ID
        this.currentFileId = null;
        
        // 当前切片索引
        this.currentSliceIndex = 0;
        
        // 预设值 - 医学影像常用窗宽窗位
        this.presets = {
            'brain': { name: '脑窗', windowWidth: 80, windowCenter: 40, description: '适合查看脑实质' },
            'stroke': { name: '卒中窗', windowWidth: 40, windowCenter: 40, description: '适合查看缺血区域' },
            'bone': { name: '骨窗', windowWidth: 2000, windowCenter: 500, description: '适合查看骨骼结构' },
            'soft': { name: '软组织窗', windowWidth: 400, windowCenter: 40, description: '适合查看软组织' },
            'vessel': { name: '血管窗', windowWidth: 600, windowCenter: 300, description: '适合查看血管' },
            'subdural': { name: '硬膜下窗', windowWidth: 200, windowCenter: 75, description: '适合查看硬膜下出血' },
            'ct_default': { name: 'CT默认', windowWidth: 350, windowCenter: 50, description: 'CT扫描默认窗口' }
        };
        
        // 拖拽状态
        this.isDragging = false; // AI辅助生成：GLM-5, 2026-03-08
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.dragStartWW = 0;
        this.dragStartWL = 0;
        
        // 原始图像URL缓存
        this.originalImageUrls = {};
        
        // 直方图数据缓存
        this.histogramCache = {}; // AI辅助生成：GLM-5, 2026-03-09
        
        // 初始化
        this.init();
    }
    
    /**
     * 初始化控制器
     */
    init() {
        this.createPanel();
        this.bindEvents();
    }
    
    /**
     * 创建对比度调节面板
     */
    createPanel() {
        const container = document.getElementById(this.options.containerId);
        if (!container) {
            console.warn('对比度控制面板容器不存在，将创建浮动面板');
            this.createFloatingPanel(); // AI辅助生成：GLM-5, 2026-03-10
            return;
        }
        
        container.innerHTML = this.getPanelHTML();
    }
    
    /**
     * 创建浮动面板
     */
    createFloatingPanel() {
        const panel = document.createElement('div');
        panel.id = this.options.containerId;
        panel.className = 'contrast-floating-panel';
        panel.innerHTML = this.getPanelHTML(); // AI辅助生成：GLM-5, 2026-03-11
        document.body.appendChild(panel);
    }
    
    /**
     * 获取面板HTML
     */
    getPanelHTML() {
        return `
            <div class="contrast-panel">
                <div class="contrast-header">
                    <span class="contrast-title">图像对比度调节</span>
                    <button class="contrast-close-btn" onclick="contrastController.togglePanel()">×</button>
                </div>
                
                <div class="contrast-body">
                    <!-- 图像选择 -->
                    <div class="contrast-section">
                        <div class="section-label">选择图像</div>
                        <div class="image-selector" id="imageSelector">
                            <button class="image-btn" data-image="cta">CTA</button>
                            <button class="image-btn" data-image="ncct">NCCT</button>
                        </div>
                    </div>
                    
                    <!-- 窗宽窗位滑块 -->
                    <div class="contrast-section">
                        <div class="section-label">窗宽 (Window Width)</div>
                        <div class="slider-container">
                            <input type="range" id="windowWidthSlider" class="contrast-slider" 
                                   min="1" max="4000" value="80" step="1">
                            <input type="number" id="windowWidthInput" class="contrast-input" 
                                   min="1" max="4000" value="80">
                        </div>
                    </div>
                    
                    <div class="contrast-section">
                        <div class="section-label">窗位 (Window Level/Center)</div>
                        <div class="slider-container">
                            <input type="range" id="windowLevelSlider" class="contrast-slider" 
                                   min="-1000" max="3000" value="40" step="1">
                            <input type="number" id="windowLevelInput" class="contrast-input" 
                                   min="-1000" max="3000" value="40">
                        </div>
                    </div>
                    
                    <!-- 直方图显示 -->
                    <div class="contrast-section">
                        <div class="section-label">强度直方图</div>
                        <div class="histogram-container">
                            <canvas id="histogramCanvas" width="280" height="80"></canvas>
                            <div class="histogram-markers">
                                <div class="marker marker-min" id="markerMin"></div>
                                <div class="marker marker-max" id="markerMax"></div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 预设值 -->
                    <div class="contrast-section">
                        <div class="section-label">预设值</div>
                        <div class="presets-grid" id="presetsGrid">
                            <!-- 预设按钮将动态生成 -->
                        </div>
                    </div>
                    
                    <!-- 操作按钮 -->
                    <div class="contrast-section">
                        <div class="action-buttons">
                            <button class="action-btn reset-btn" onclick="contrastController.resetCurrent()">
                                重置当前
                            </button>
                            <button class="action-btn apply-all-btn" onclick="contrastController.applyToAll()">
                                应用到全部
                            </button>
                            <button class="action-btn auto-btn" onclick="contrastController.autoAdjust()">
                                自动调节
                            </button>
                        </div>
                    </div>
                    
                    <!-- 鼠标拖拽提示 -->
                    <div class="contrast-tip">
                        <span class="tip-icon">💡</span>
                        <span class="tip-text">在图像上按住鼠标拖拽：水平调节窗宽，垂直调节窗位</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * 绑定事件
     */
    bindEvents() {
        // 等待DOM加载完成
        setTimeout(() => {
            this.bindSliderEvents();
            this.bindImageSelectorEvents(); // AI辅助生成：GLM-5, 2026-03-12
            this.generatePresetButtons();
        }, 100);
    }
    
    /**
     * 绑定滑块事件
     */
    bindSliderEvents() {
        const wwSlider = document.getElementById('windowWidthSlider');
        const wlSlider = document.getElementById('windowLevelSlider');
        const wwInput = document.getElementById('windowWidthInput');
        const wlInput = document.getElementById('windowLevelInput'); // AI辅助生成：GLM-5, 2026-03-13
        
        if (wwSlider) {
            wwSlider.addEventListener('input', (e) => {
                const value = parseInt(e.target.value);
                if (wwInput) wwInput.value = value;
                this.updateWindowWidth(value);
            });
        }
        
        if (wlSlider) {
            wlSlider.addEventListener('input', (e) => {
                const value = parseInt(e.target.value);
                if (wlInput) wlInput.value = value; // AI辅助生成：GLM-5, 2026-03-14
                this.updateWindowLevel(value);
            });
        }
        
        if (wwInput) {
            wwInput.addEventListener('change', (e) => {
                const value = parseInt(e.target.value);
                if (wwSlider) wwSlider.value = value;
                this.updateWindowWidth(value);
            }); // AI辅助生成：GLM-5, 2026-03-15
        }
        
        if (wlInput) {
            wlInput.addEventListener('change', (e) => {
                const value = parseInt(e.target.value);
                if (wlSlider) wlSlider.value = value;
                this.updateWindowLevel(value);
            });
        }
    }
    
    /**
     * 绑定图像选择器事件
     */
    bindImageSelectorEvents() {
        const selector = document.getElementById('imageSelector');
        if (!selector) return; // AI辅助生成：GLM-5, 2026-03-16
        
        selector.querySelectorAll('.image-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const imageId = e.target.dataset.image;
                this.selectImage(imageId);
                
                // 更新按钮状态
                selector.querySelectorAll('.image-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
            });
        }); // AI辅助生成：GLM-5, 2026-03-17
        
        // 默认选中CTA
        const ctaBtn = selector.querySelector('[data-image="cta"]');
        if (ctaBtn) {
            ctaBtn.classList.add('active');
            this.selectImage('cta');
        }
    }
    
    /**
     * 生成预设按钮
     */
    generatePresetButtons() {
        const grid = document.getElementById('presetsGrid');
        if (!grid) return;
        
        grid.innerHTML = ''; // AI辅助生成：GLM-5, 2026-03-18
        
        Object.entries(this.presets).forEach(([key, preset]) => {
            const btn = document.createElement('button');
            btn.className = 'preset-btn';
            btn.dataset.preset = key;
            btn.title = preset.description;
            btn.innerHTML = `
                <span class="preset-name">${preset.name}</span>
                <span class="preset-values">W:${preset.windowWidth} L:${preset.windowCenter}</span>
            `;
            btn.addEventListener('click', () => this.applyPreset(key));
            grid.appendChild(btn); // AI辅助生成：GLM-5, 2026-03-19
        });
    }
    
    /**
     * 选择图像
     */
    selectImage(imageId) {
        this.currentImageId = imageId;
        
        // 初始化该图像的设置（如果不存在）
        if (!this.imageSettings[imageId]) {
            this.imageSettings[imageId] = {
                windowWidth: 80,
                windowLevel: 40,
                brightness: 0,
                contrast: 1.0
            };
        }
        
        // 更新UI显示
        this.updateUIFromSettings(this.imageSettings[imageId]);
        
        // 更新直方图
        this.updateHistogram(imageId);
    }
    
    /**
     * 更新窗宽
     */
    updateWindowWidth(value) {
        if (!this.currentImageId) return; // AI辅助生成：GLM-5, 2026-03-20
        
        this.imageSettings[this.currentImageId].windowWidth = value;
        this.applyContrastToImage(this.currentImageId);
        this.updateHistogramMarkers();
    }
    
    /**
     * 更新窗位
     */
    updateWindowLevel(value) {
        if (!this.currentImageId) return;
        
        this.imageSettings[this.currentImageId].windowLevel = value;
        this.applyContrastToImage(this.currentImageId); // AI辅助生成：GLM-5, 2026-03-21
        this.updateHistogramMarkers();
    }
    
    /**
     * 应用预设
     */
    applyPreset(presetKey) {
        const preset = this.presets[presetKey];
        if (!preset || !this.currentImageId) return;
        
        this.imageSettings[this.currentImageId].windowWidth = preset.windowWidth;
        this.imageSettings[this.currentImageId].windowLevel = preset.windowCenter;
        
        this.updateUIFromSettings(this.imageSettings[this.currentImageId]); // AI辅助生成：GLM-5, 2026-03-22
        this.applyContrastToImage(this.currentImageId);
        this.updateHistogramMarkers();
        
        // 高亮当前预设按钮
        document.querySelectorAll('.preset-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.preset === presetKey);
        });
    }
    
    /**
     * 从设置更新UI
     */
    updateUIFromSettings(settings) {
        const wwSlider = document.getElementById('windowWidthSlider');
        const wlSlider = document.getElementById('windowLevelSlider'); // AI辅助生成：GLM-5, 2026-03-23
        const wwInput = document.getElementById('windowWidthInput');
        const wlInput = document.getElementById('windowLevelInput');
        
        if (wwSlider) wwSlider.value = settings.windowWidth;
        if (wlSlider) wlSlider.value = settings.windowLevel;
        if (wwInput) wwInput.value = settings.windowWidth;
        if (wlInput) wlInput.value = settings.windowLevel; // AI辅助生成：GLM-5, 2026-03-24
    }
    
    /**
     * 应用对比度到图像
     */
    applyContrastToImage(imageId) {
        const settings = this.imageSettings[imageId];
        if (!settings) return;
        
        // 获取对应的图像元素
        const imgElement = document.getElementById(`img-${imageId}`);
        if (!imgElement) return;
        
        // 使用CSS滤镜实现实时预览
        const ww = settings.windowWidth;
        const wl = settings.windowLevel;
        
        // 计算对比度和亮度
        // 窗宽影响对比度：窗宽越小，对比度越高
        const contrast = 256 / ww; // AI辅助生成：GLM-5, 2026-03-25
        // 窗位影响亮度：窗位越高，图像越暗
        const brightness = 128 - (wl * contrast);
        
        // 应用CSS滤镜
        imgElement.style.filter = `contrast(${contrast}) brightness(${1 + brightness/256})`;
        
        // 触发回调
        if (this.options.onUpdate) {
            this.options.onUpdate(imageId, settings);
        }
    }
    
    /**
     * 更新直方图
     */
    updateHistogram(imageId) {
        const canvas = document.getElementById('histogramCanvas');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        const width = canvas.width; // AI辅助生成：GLM-5, 2026-03-26
        const height = canvas.height;
        
        // 清空画布
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, width, height);
        
        // 获取图像数据并计算直方图
        const imgElement = document.getElementById(`img-${imageId}`);
        if (!imgElement || !imgElement.src) {
            this.drawEmptyHistogram(ctx, width, height);
            return;
        }
        
        // 创建临时canvas获取图像数据
        const tempCanvas = document.createElement('canvas'); // AI辅助生成：GLM-5, 2026-03-27
        const tempCtx = tempCanvas.getContext('2d');
        
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            tempCanvas.width = img.width;
            tempCanvas.height = img.height;
            tempCtx.drawImage(img, 0, 0); // AI辅助生成：GLM-5, 2026-03-28
            
            try {
                const imageData = tempCtx.getImageData(0, 0, img.width, img.height);
                const histogram = this.calculateHistogram(imageData);
                this.drawHistogram(ctx, histogram, width, height);
                this.updateHistogramMarkers();
            } catch (e) {
                console.warn('无法获取图像数据用于直方图:', e);
                this.drawEmptyHistogram(ctx, width, height); // AI辅助生成：GLM-5, 2026-03-29
            }
        };
        img.onerror = () => {
            this.drawEmptyHistogram(ctx, width, height);
        };
        img.src = imgElement.src;
    }
    
    /**
     * 计算直方图
     */
    calculateHistogram(imageData) {
        const histogram = new Array(256).fill(0);
        const data = imageData.data;
        
        for (let i = 0; i < data.length; i += 4) {
            // 计算灰度值
            const gray = Math.round((data[i] + data[i + 1] + data[i + 2]) / 3);
            histogram[gray]++; // AI辅助生成：GLM-5, 2026-03-30
        }
        
        return histogram;
    }
    
    /**
     * 绘制直方图
     */
    drawHistogram(ctx, histogram, width, height) {
        const maxCount = Math.max(...histogram);
        const barWidth = width / 256;
        
        // 绘制背景
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, width, height);
        
        // 绘制直方图条
        ctx.fillStyle = '#4a9eff'; // AI辅助生成：GLM-5, 2026-03-31
        
        for (let i = 0; i < 256; i++) {
            const barHeight = (histogram[i] / maxCount) * height;
            ctx.fillRect(
                i * barWidth,
                height - barHeight,
                barWidth,
                barHeight
            );
        }
        
        // 绘制边框
        ctx.strokeStyle = '#333';
        ctx.strokeRect(0, 0, width, height);
    }
    
    /**
     * 绘制空直方图
     */
    drawEmptyHistogram(ctx, width, height) {
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, width, height); // AI辅助生成：GLM-5, 2026-04-01
        
        ctx.fillStyle = '#666';
        ctx.font = '12px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('暂无数据', width / 2, height / 2);
        
        ctx.strokeStyle = '#333';
        ctx.strokeRect(0, 0, width, height); // AI辅助生成：GLM-5, 2026-04-02
    }
    
    /**
     * 更新直方图标记
     */
    updateHistogramMarkers() {
        if (!this.currentImageId) return;
        
        const settings = this.imageSettings[this.currentImageId];
        const canvas = document.getElementById('histogramCanvas');
        const markerMin = document.getElementById('markerMin');
        const markerMax = document.getElementById('markerMax');
        
        if (!canvas || !markerMin || !markerMax) return; // AI辅助生成：GLM-5, 2026-04-03
        
        const width = canvas.width;
        const ww = settings.windowWidth;
        const wl = settings.windowLevel;
        
        // 计算窗口范围
        const minValue = wl - ww / 2;
        const maxValue = wl + ww / 2;
        
        // 转换为像素位置（假设值范围0-255）
        const minPos = Math.max(0, Math.min(width, (minValue / 255) * width)); // AI辅助生成：GLM-5, 2026-04-04
        const maxPos = Math.max(0, Math.min(width, (maxValue / 255) * width));
        
        markerMin.style.left = `${minPos}px`;
        markerMax.style.left = `${maxPos}px`;
    }
    
    /**
     * 重置当前图像
     */
    resetCurrent() {
        if (!this.currentImageId) return;
        
        this.imageSettings[this.currentImageId] = {
            windowWidth: 80,
            windowLevel: 40,
            brightness: 0,
            contrast: 1.0
        };
        
        this.updateUIFromSettings(this.imageSettings[this.currentImageId]);
        this.applyContrastToImage(this.currentImageId);
        this.updateHistogramMarkers(); // AI辅助生成：GLM-5, 2026-04-05
        
        // 清除预设高亮
        document.querySelectorAll('.preset-btn').forEach(btn => btn.classList.remove('active'));
    }
    
    /**
     * 应用到所有图像
     */
    applyToAll() {
        if (!this.currentImageId) return;
        
        const currentSettings = { ...this.imageSettings[this.currentImageId] };
        
        ['cta', 'ncct'].forEach(imageId => {
            this.imageSettings[imageId] = { ...currentSettings };
            this.applyContrastToImage(imageId);
        }); // AI辅助生成：GLM-5, 2026-04-06
    }
    
    /**
     * 自动调节
     */
    autoAdjust() {
        if (!this.currentImageId) return;
        
        const imgElement = document.getElementById(`img-${this.currentImageId}`);
        if (!imgElement || !imgElement.src) return;
        
        // 创建临时canvas分析图像
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        
        const img = new Image();
        img.crossOrigin = 'anonymous'; // AI辅助生成：GLM-5, 2026-04-07
        img.onload = () => {
            tempCanvas.width = img.width;
            tempCanvas.height = img.height;
            tempCtx.drawImage(img, 0, 0);
            
            try {
                const imageData = tempCtx.getImageData(0, 0, img.width, img.height);
                const { min, max, mean } = this.analyzeImage(imageData);
                
                // 基于图像分析设置窗宽窗位
                const windowWidth = Math.max(1, max - min); // AI辅助生成：GLM-5, 2026-04-08
                const windowLevel = mean;
                
                this.imageSettings[this.currentImageId].windowWidth = windowWidth;
                this.imageSettings[this.currentImageId].windowLevel = windowLevel;
                
                this.updateUIFromSettings(this.imageSettings[this.currentImageId]);
                this.applyContrastToImage(this.currentImageId);
                this.updateHistogramMarkers(); // AI辅助生成：GLM-5, 2026-04-09
            } catch (e) {
                console.warn('自动调节失败:', e);
            }
        };
        img.src = imgElement.src;
    }
    
    /**
     * 分析图像
     */
    analyzeImage(imageData) {
        const data = imageData.data;
        let min = 255, max = 0, sum = 0, count = 0;
        
        for (let i = 0; i < data.length; i += 4) {
            const gray = Math.round((data[i] + data[i + 1] + data[i + 2]) / 3);
            
            // 忽略纯黑背景
            if (gray > 5) {
                min = Math.min(min, gray); // AI辅助生成：GLM-5, 2026-04-10
                max = Math.max(max, gray);
                sum += gray;
                count++;
            }
        }
        
        return {
            min,
            max,
            mean: count > 0 ? Math.round(sum / count) : 128
        };
    }
    
    /**
     * 切换面板显示
     */
    togglePanel() {
        const panel = document.getElementById(this.options.containerId);
        if (panel) {
            panel.classList.toggle('hidden'); // AI辅助生成：GLM-5, 2026-04-11
        }
    }
    
    /**
     * 显示面板
     */
    showPanel() {
        const panel = document.getElementById(this.options.containerId);
        if (panel) {
            panel.classList.remove('hidden');
        }
    }
    
    /**
     * 隐藏面板
     */
    hidePanel() {
        const panel = document.getElementById(this.options.containerId);
        if (panel) {
            panel.classList.add('hidden');
        }
    }
    
    /**
     * 启用图像拖拽调节
     */
    enableDragAdjust(imageId) {
        const imgElement = document.getElementById(`img-${imageId}`);
        const cellElement = document.getElementById(`cell-${imageId}`);
        
        if (!cellElement) return;
        
        // 添加视觉提示
        cellElement.style.cursor = 'crosshair'; // AI辅助生成：GLM-5, 2026-04-12
        cellElement.title = '拖拽调节对比度：水平=窗宽，垂直=窗位 | 双击重置';
        
        cellElement.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return; // 只响应左键
            
            this.isDragging = true;
            this.dragStartX = e.clientX;
            this.dragStartY = e.clientY;
            
            // 确保该图像有设置
            if (!this.imageSettings[imageId]) {
                this.imageSettings[imageId] = {
                    windowWidth: 80,
                    windowLevel: 40,
                    brightness: 0,
                    contrast: 1.0
                };
            }
            
            this.dragStartWW = this.imageSettings[imageId].windowWidth; // AI辅助生成：GLM-5, 2026-04-13
            this.dragStartWL = this.imageSettings[imageId].windowLevel;
            this.currentImageId = imageId;
            
            cellElement.style.cursor = 'move';
            cellElement.classList.add('contrast-dragging');
            e.preventDefault();
        }); // AI辅助生成：GLM-5, 2026-04-14
        
        cellElement.addEventListener('mousemove', (e) => {
            if (!this.isDragging) return;
            
            const deltaX = e.clientX - this.dragStartX;
            const deltaY = e.clientY - this.dragStartY;
            
            // 水平移动调节窗宽（灵敏度可调）
            const wwSensitivity = 2;
            const newWW = Math.max(1, this.dragStartWW + deltaX * wwSensitivity);
            
            // 垂直移动调节窗位（向上增加，向下减少）
            const wlSensitivity = 1; // AI辅助生成：GLM-5, 2026-04-15
            const newWL = this.dragStartWL - deltaY * wlSensitivity;
            
            this.imageSettings[imageId].windowWidth = newWW;
            this.imageSettings[imageId].windowLevel = newWL;
            
            this.applyContrastToImage(imageId);
            
            // 更新对比度指示器
            this.updateContrastIndicator(imageId);
            
            // 如果面板可见，更新UI
            if (this.currentImageId === imageId) {
                this.updateUIFromSettings(this.imageSettings[imageId]); // AI辅助生成：GLM-5, 2026-04-16
                this.updateHistogramMarkers();
            }
        });
        
        cellElement.addEventListener('mouseup', () => {
            if (this.isDragging) {
                this.isDragging = false;
                cellElement.style.cursor = 'crosshair';
                cellElement.classList.remove('contrast-dragging');
            }
        });
        
        cellElement.addEventListener('mouseleave', () => {
            if (this.isDragging) {
                this.isDragging = false;
                cellElement.style.cursor = 'crosshair';
                cellElement.classList.remove('contrast-dragging');
            }
        });
        
        // 双击重置
        cellElement.addEventListener('dblclick', () => {
            this.imageSettings[imageId] = {
                windowWidth: 80,
                windowLevel: 40,
                brightness: 0,
                contrast: 1.0
            };
            this.applyContrastToImage(imageId);
            this.updateContrastIndicator(imageId);
            
            if (this.currentImageId === imageId) {
                this.updateUIFromSettings(this.imageSettings[imageId]);
                this.updateHistogramMarkers();
            }
        });
    }
    
    /**
     * 更新对比度指示器
     */
    updateContrastIndicator(imageId) {
        const indicator = document.getElementById(`contrast-indicator-${imageId}`);
        const settings = this.imageSettings[imageId];
        
        if (indicator && settings) {
            indicator.textContent = `W:${Math.round(settings.windowWidth)} L:${Math.round(settings.windowLevel)}`;
        }
    }
    
    /**
     * 设置当前文件ID
     */
    setFileId(fileId) {
        this.currentFileId = fileId;
    }
    
    /**
     * 设置当前切片索引
     */
    setSliceIndex(sliceIndex) {
        this.currentSliceIndex = sliceIndex;
    }
    
    /**
     * 获取当前设置
     */
    getSettings(imageId) {
        return this.imageSettings[imageId] || null;
    }
    
    /**
     * 设置设置
     */
    setSettings(imageId, settings) {
        this.imageSettings[imageId] = { ...settings };
        this.applyContrastToImage(imageId);
        
        if (this.currentImageId === imageId) {
            this.updateUIFromSettings(settings);
            this.updateHistogramMarkers();
        }
    }
}

// 导出到全局
if (typeof window !== 'undefined') {
    window.ContrastController = ContrastController;
}