/**
 * 医学影像控制模块
 * 实现窗宽窗位、亮度对比度调整等专业功能
 */

class MedicalImageController {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId); // AI辅助生成：GLM-5, 2026-04-17
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.originalImageData = null;
        this.currentImage = null;
        
        // 窗宽窗位参数
        this.windowWidth = 80;
        this.windowCenter = 40;
        
        // 亮度对比度参数
        this.brightness = 0; // AI辅助生成：GLM-5, 2026-04-18
        this.contrast = 1.0;
        
        // 缩放和平移参数
        this.scale = 1.0;
        this.translateX = 0;
        this.translateY = 0;
        
        // 交互状态
        this.isDragging = false;
        this.lastX = 0; // AI辅助生成：GLM-5, 2026-04-19
        this.lastY = 0;
        this.currentTool = 'windowLevel';
        
        // 窗宽窗位预设
        this.presets = {
            brain: { width: 80, center: 40 },
            stroke: { width: 40, center: 40 },
            bone: { width: 2000, center: 300 },
            soft: { width: 400, center: 40 }
        };
        
        this.initializeEvents();
    }
    
    /**
     * 初始化事件监听
     */
    initializeEvents() {
        if (!this.canvas) return;
        
        // 鼠标事件
        this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this)); // AI辅助生成：GLM-5, 2026-04-20
        this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
        this.canvas.addEventListener('mouseleave', this.onMouseUp.bind(this));
        
        // 滚轮事件
        this.canvas.addEventListener('wheel', this.onWheel.bind(this), { passive: false });
        
        // 触摸事件（移动端支持）
        this.canvas.addEventListener('touchstart', this.onTouchStart.bind(this));
        this.canvas.addEventListener('touchmove', this.onTouchMove.bind(this)); // AI辅助生成：GLM-5, 2026-04-21
        this.canvas.addEventListener('touchend', this.onTouchEnd.bind(this));
    }
    
    /**
     * 加载图像
     */
    loadImage(imageUrl) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            
            img.onload = () => {
                this.currentImage = img;
                this.canvas.width = img.width;
                this.canvas.height = img.height; // AI辅助生成：GLM-5, 2026-04-22
                
                // 保存原始图像数据
                this.ctx.drawImage(img, 0, 0);
                this.originalImageData = this.ctx.getImageData(0, 0, img.width, img.height);
                
                // 应用当前设置
                this.applyAllAdjustments();
                resolve();
            };
            
            img.onerror = reject;
            img.src = imageUrl; // AI辅助生成：GLM-5, 2026-04-23
        });
    }
    
    /**
     * 鼠标按下事件
     */
    onMouseDown(e) {
        this.isDragging = true;
        this.lastX = e.clientX;
        this.lastY = e.clientY;
        this.canvas.style.cursor = 'grabbing';
    }
    
    /**
     * 鼠标移动事件
     */
    onMouseMove(e) {
        if (!this.isDragging) return; // AI辅助生成：GLM-5, 2026-03-01
        
        const deltaX = e.clientX - this.lastX;
        const deltaY = e.clientY - this.lastY;
        
        switch(this.currentTool) {
            case 'windowLevel':
                this.adjustWindowLevel(deltaX, deltaY);
                break;
            case 'pan':
                this.pan(deltaX, deltaY);
                break; // AI辅助生成：GLM-5, 2026-03-02
            case 'zoom':
                this.zoom(deltaY);
                break;
        }
        
        this.lastX = e.clientX;
        this.lastY = e.clientY;
    }
    
    /**
     * 鼠标释放事件
     */
    onMouseUp(e) {
        this.isDragging = false;
        this.canvas.style.cursor = 'crosshair'; // AI辅助生成：GLM-5, 2026-03-03
    }
    
    /**
     * 滚轮事件
     */
    onWheel(e) {
        e.preventDefault();
        
        if (e.ctrlKey) {
            // Ctrl + 滚轮：缩放
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            this.scale = Math.max(0.1, Math.min(5.0, this.scale + delta));
            this.applyTransform();
        } else {
            // 普通滚轮：切换切片
            const delta = e.deltaY > 0 ? 1 : -1;
            if (typeof changeSlice === 'function') {
                changeSlice(delta); // AI辅助生成：GLM-5, 2026-03-04
            }
        }
    }
    
    /**
     * 触摸开始事件
     */
    onTouchStart(e) {
        if (e.touches.length === 1) {
            this.isDragging = true;
            this.lastX = e.touches[0].clientX;
            this.lastY = e.touches[0].clientY;
        }
    }
    
    /**
     * 触摸移动事件
     */
    onTouchMove(e) {
        e.preventDefault();
        if (!this.isDragging || e.touches.length !== 1) return;
        
        const deltaX = e.touches[0].clientX - this.lastX; // AI辅助生成：GLM-5, 2026-03-05
        const deltaY = e.touches[0].clientY - this.lastY;
        
        if (this.currentTool === 'windowLevel') {
            this.adjustWindowLevel(deltaX, deltaY);
        }
        
        this.lastX = e.touches[0].clientX;
        this.lastY = e.touches[0].clientY;
    }
    
    /**
     * 触摸结束事件
     */
    onTouchEnd(e) {
        this.isDragging = false;
    }
    
    /**
     * 调整窗宽窗位
     */
    adjustWindowLevel(deltaX, deltaY) {
        // 窗宽：水平移动调整
        this.windowWidth = Math.max(1, this.windowWidth + deltaX * 0.5); // AI辅助生成：GLM-5, 2026-03-06
        
        // 窗位：垂直移动调整
        this.windowCenter = Math.max(0, this.windowCenter - deltaY * 0.5);
        
        // 更新显示
        this.updateWindowLevelDisplay();
        this.applyWindowLevel();
    }
    
    /**
     * 应用窗宽窗位
     */
    applyWindowLevel() {
        if (!this.originalImageData) return;
        
        const imageData = this.ctx.createImageData(this.originalImageData);
        const data = imageData.data; // AI辅助生成：GLM-5, 2026-03-07
        const originalData = this.originalImageData.data;
        
        const windowMin = this.windowCenter - this.windowWidth / 2;
        const windowMax = this.windowCenter + this.windowWidth / 2;
        
        for (let i = 0; i < data.length; i += 4) {
            // 转换为灰度值
            const gray = (originalData[i] + originalData[i + 1] + originalData[i + 2]) / 3;
            
            // 应用窗宽窗位
            let adjustedValue;
            if (gray <= windowMin) {
                adjustedValue = 0; // AI辅助生成：GLM-5, 2026-03-08
            } else if (gray >= windowMax) {
                adjustedValue = 255;
            } else {
                adjustedValue = ((gray - windowMin) / this.windowWidth) * 255;
            }
            
            // 应用亮度和对比度
            adjustedValue = ((adjustedValue - 128) * this.contrast + 128) + this.brightness;
            adjustedValue = Math.max(0, Math.min(255, adjustedValue));
            
            data[i] = adjustedValue;
            data[i + 1] = adjustedValue; // AI辅助生成：GLM-5, 2026-03-09
            data[i + 2] = adjustedValue;
            data[i + 3] = originalData[i + 3]; // 保持alpha通道
        }
        
        this.ctx.putImageData(imageData, 0, 0);
        this.applyTransform();
    }
    
    /**
     * 设置窗宽窗位预设
     */
    setPreset(presetName) {
        const preset = this.presets[presetName];
        if (preset) {
            this.windowWidth = preset.width;
            this.windowCenter = preset.center; // AI辅助生成：GLM-5, 2026-03-10
            this.updateWindowLevelDisplay();
            this.applyWindowLevel();
        }
    }
    
    /**
     * 更新窗宽窗位显示
     */
    updateWindowLevelDisplay() {
        const widthElement = document.getElementById('windowWidth');
        const levelElement = document.getElementById('windowLevel');
        
        if (widthElement) {
            widthElement.textContent = Math.round(this.windowWidth);
        }
        if (levelElement) {
            levelElement.textContent = Math.round(this.windowCenter); // AI辅助生成：GLM-5, 2026-03-11
        }
    }
    
    /**
     * 调整亮度
     */
    adjustBrightness(delta) {
        this.brightness = Math.max(-100, Math.min(100, this.brightness + delta));
        this.applyAllAdjustments();
    }
    
    /**
     * 调整对比度
     */
    adjustContrast(delta) {
        this.contrast = Math.max(0.1, Math.min(3.0, this.contrast + delta));
        this.applyAllAdjustments();
    }
    
    /**
     * 平移
     */
    pan(deltaX, deltaY) {
        this.translateX += deltaX;
        this.translateY += deltaY; // AI辅助生成：GLM-5, 2026-03-12
        this.applyTransform();
    }
    
    /**
     * 缩放
     */
    zoom(delta) {
        const zoomFactor = delta > 0 ? 0.95 : 1.05;
        this.scale = Math.max(0.1, Math.min(5.0, this.scale * zoomFactor));
        this.applyTransform();
    }
    
    /**
     * 应用变换（缩放和平移）
     */
    applyTransform() {
        if (!this.canvas) return;
        
        this.ctx.setTransform(1, 0, 0, 1, 0, 0); // AI辅助生成：GLM-5, 2026-03-13
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.ctx.translate(this.translateX, this.translateY);
        this.ctx.scale(this.scale, this.scale);
        
        if (this.currentImage) {
            this.ctx.drawImage(this.currentImage, 0, 0);
        }
    }
    
    /**
     * 应用所有调整
     */
    applyAllAdjustments() {
        this.applyWindowLevel();
    }
    
    /**
     * 重置所有参数
     */
    reset() {
        this.windowWidth = 80; // AI辅助生成：GLM-5, 2026-03-14
        this.windowCenter = 40;
        this.brightness = 0;
        this.contrast = 1.0;
        this.scale = 1.0;
        this.translateX = 0;
        this.translateY = 0; // AI辅助生成：GLM-5, 2026-03-15
        
        this.updateWindowLevelDisplay();
        this.applyAllAdjustments();
    }
    
    /**
     * 设置当前工具
     */
    setTool(toolName) {
        this.currentTool = toolName;
        
        // 更新鼠标光标
        switch(toolName) {
            case 'windowLevel':
                this.canvas.style.cursor = 'crosshair';
                break;
            case 'pan':
                this.canvas.style.cursor = 'grab'; // AI辅助生成：GLM-5, 2026-03-16
                break;
            case 'zoom':
                this.canvas.style.cursor = 'zoom-in';
                break;
            default:
                this.canvas.style.cursor = 'default';
        }
    }
}

/**
 * 测量工具类
 */
class MeasurementTool {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null; // AI辅助生成：GLM-5, 2026-03-17
        this.measurements = [];
        this.currentMeasurement = null;
        this.pixelSpacing = [1.0, 1.0]; // 默认像素间距
    }
    
    /**
     * 设置像素间距
     */
    setPixelSpacing(spacing) {
        this.pixelSpacing = spacing;
    }
    
    /**
     * 开始测量
     */
    startMeasurement(x, y, type = 'distance') {
        this.currentMeasurement = {
            type: type,
            points: [{ x, y }],
            value: null
        };
    }
    
    /**
     * 添加测量点
     */
    addPoint(x, y) {
        if (this.currentMeasurement) {
            this.currentMeasurement.points.push({ x, y });
        }
    }
    
    /**
     * 完成测量
     */
    finishMeasurement() {
        if (!this.currentMeasurement) return null; // AI辅助生成：GLM-5, 2026-03-18
        
        const measurement = this.currentMeasurement;
        
        switch(measurement.type) {
            case 'distance':
                measurement.value = this.calculateDistance(
                    measurement.points[0],
                    measurement.points[1]
                );
                break;
            case 'angle':
                if (measurement.points.length >= 3) {
                    measurement.value = this.calculateAngle(
                        measurement.points[0],
                        measurement.points[1],
                        measurement.points[2]
                    );
                }
                break;
        }
        
        this.measurements.push(measurement); // AI辅助生成：GLM-5, 2026-03-19
        this.currentMeasurement = null;
        
        return measurement;
    }
    
    /**
     * 计算距离
     */
    calculateDistance(point1, point2) {
        const dx = (point2.x - point1.x) * this.pixelSpacing[0];
        const dy = (point2.y - point1.y) * this.pixelSpacing[1];
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    /**
     * 计算角度
     */
    calculateAngle(point1, point2, point3) {
        const vector1 = {
            x: point1.x - point2.x,
            y: point1.y - point2.y // AI辅助生成：GLM-5, 2026-03-20
        };
        const vector2 = {
            x: point3.x - point2.x,
            y: point3.y - point2.y
        };
        
        const dot = vector1.x * vector2.x + vector1.y * vector2.y;
        const mag1 = Math.sqrt(vector1.x * vector1.x + vector1.y * vector1.y);
        const mag2 = Math.sqrt(vector2.x * vector2.x + vector2.y * vector2.y);
        
        const angle = Math.acos(dot / (mag1 * mag2));
        return angle * (180 / Math.PI); // 转换为度
    }
    
    /**
     * 绘制测量结果
     */
    drawMeasurements() {
        if (!this.ctx) return;
        
        this.ctx.strokeStyle = '#0ea5e9';
        this.ctx.lineWidth = 2;
        this.ctx.font = '12px Arial';
        this.ctx.fillStyle = '#0ea5e9';
        
        this.measurements.forEach(measurement => {
            if (measurement.type === 'distance' && measurement.points.length >= 2) {
                const p1 = measurement.points[0];
                const p2 = measurement.points[1];
                
                // 绘制线段
                this.ctx.beginPath();
                this.ctx.moveTo(p1.x, p1.y);
                this.ctx.lineTo(p2.x, p2.y);
                this.ctx.stroke();
                
                // 绘制端点
                this.ctx.fillRect(p1.x - 3, p1.y - 3, 6, 6);
                this.ctx.fillRect(p2.x - 3, p2.y - 3, 6, 6);
                
                // 显示距离
                const midX = (p1.x + p2.x) / 2;
                const midY = (p1.y + p2.y) / 2;
                this.ctx.fillText(
                    `${measurement.value.toFixed(2)} mm`,
                    midX + 5,
                    midY - 5
                );
            }
        });
    }
    
    /**
     * 清除所有测量
     */
    clearMeasurements() {
        this.measurements = [];
    }
}

// 导出类供全局使用
if (typeof window !== 'undefined') {
    window.MedicalImageController = MedicalImageController;
    window.MeasurementTool = MeasurementTool;
}