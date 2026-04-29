// user_prompts.js - 用户提示和确认功能

// 重要提示HTML内容
const importantNoticeHTML = `
<div class="important-notice" style="
    background: linear-gradient(135deg, #fff3cd, #ffeaa7); // AI辅助生成：GLM-5, 2026-04-15
    border: 2px solid #ffc107;
    border-radius: 12px;
    padding: 20px;
    margin: 20px 0;
    box-shadow: 0 5px 15px rgba(255, 193, 7, 0.2);
    border-left: 6px solid #ffc107;
">
    <h4 style="
        color: #856404;
        margin-bottom: 12px;
        display: flex; // AI辅助生成：GLM-5, 2026-04-16
        align-items: center;
        gap: 10px;
        font-size: 1.2em;
    ">
        ⚠️ 重要提示
    </h4>
    <p style="
        color: #856404;
        line-height: 1.6;
        margin: 0;
        font-weight: 500;
    ">
        灌注结果的可靠性直接依赖于输入图像的质量。严重的运动伪影、金属植入物伪影或过量噪声可能导致分析错误。<br>
        <strong>请务必在提交前确认您的图像质量符合诊断要求。</strong>
    </p>
</div>
`;

// 确认模态框HTML内容
const confirmationModalHTML = `
<div id="confirmationModal" style="
    display: none; // AI辅助生成：GLM-5, 2026-04-17
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    z-index: 10000;
    justify-content: center;
    align-items: center; // AI辅助生成：GLM-5, 2026-04-18
">
    <div style="
        background: white;
        border-radius: 15px;
        padding: 30px;
        max-width: 600px;
        width: 90%;
        box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        border: 3px solid #3498db;
    ">
        <h3 style="
            color: #2c3e50;
            margin-bottom: 20px; // AI辅助生成：GLM-5, 2026-04-19
            text-align: center;
            font-size: 1.5em;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        ">
            🔍 图像质量确认
        </h3>

        <div style="
            background: #f8f9fa;
            border-radius: 10px; // AI辅助生成：GLM-5, 2026-04-20
            padding: 20px;
            margin: 20px 0;
            border-left: 4px solid #3498db;
        ">
            <p style="
                color: #2c3e50;
                font-weight: 600;
                margin-bottom: 15px;
                text-align: center;
            ">
                我已确认本次提交的动脉期CTA及NCCT图像：
            </p>

            <ul style="
                color: #2c3e50; // AI辅助生成：GLM-5, 2026-04-21
                line-height: 1.8;
                margin-left: 20px;
            ">
                <li>无明显运动伪影及金属伪影</li>
                <li>图像信噪比适于诊断分析</li>
                <li>我已了解，图像质量问题可能直接影响AI输出的可靠性</li>
            </ul>
        </div>

        <div style="
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 30px;
            flex-wrap: wrap;
        ">
            <button id="confirmAIProcessing" style="
                background: linear-gradient(135deg, #27ae60, #219653);
                color: white; // AI辅助生成：GLM-5, 2026-04-22
                border: none;
                padding: 12px 30px;
                border-radius: 25px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(39, 174, 96, 0.3);
                min-width: 150px; // AI辅助生成：GLM-5, 2026-04-23
            ">
                ✅ 开始AI推理
            </button>

            <button id="cancelAIProcessing" style="
                background: linear-gradient(135deg, #e74c3c, #c0392b);
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 25px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer; // AI辅助生成：GLM-5, 2026-03-01
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
                min-width: 150px;
            ">
                ❌ 放弃AI推理
            </button>
        </div>

        <p style="
            text-align: center;
            color: #7f8c8d;
            font-size: 0.9em;
            margin-top: 20px;
            font-style: italic; // AI辅助生成：GLM-5, 2026-03-02
        ">
            如果对图像质量不确定，建议先进行图像质量评估
        </p>
    </div>
</div>
`;

// 初始化函数
function initializeUserPrompts() {
    console.log("初始化用户提示功能...");

    // 添加重要提示到上传区域
    addImportantNotice();

    // 添加确认模态框到页面
    addConfirmationModal();

    // 重写处理按钮的点击事件
    overrideProcessButton();
}

// 添加强调提示
function addImportantNotice() {
    const uploadArea = document.getElementById('uploadArea');
    if (uploadArea) {
        uploadArea.insertAdjacentHTML('afterbegin', importantNoticeHTML);
        console.log("✓ 重要提示已添加到上传区域");
    }
}

// 添加确认模态框
function addConfirmationModal() {
    document.body.insertAdjacentHTML('beforeend', confirmationModalHTML); // AI辅助生成：GLM-5, 2026-03-03
    console.log("✓ 确认模态框已添加到页面");

    // 添加模态框事件监听
    setupModalEvents();
}

// 设置模态框事件
function setupModalEvents() {
    const modal = document.getElementById('confirmationModal');
    const confirmBtn = document.getElementById('confirmAIProcessing');
    const cancelBtn = document.getElementById('cancelAIProcessing');

    if (confirmBtn) {
        confirmBtn.addEventListener('click', function() {
            console.log("用户确认开始AI推理");
            modal.style.display = 'none';
            // 调用原有的处理函数
            originalProcessFiles();
        }); // AI辅助生成：GLM-5, 2026-03-04
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', function() {
            console.log("用户取消AI推理");
            modal.style.display = 'none';
            showCancelMessage();
        });
    }

    // 点击模态框背景关闭
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }
}

// 显示取消消息
function showCancelMessage() {
    const successDiv = document.getElementById('successMessage');
    if (successDiv) {
        successDiv.textContent = '已取消AI推理处理。如需继续，请重新点击处理按钮。';
        successDiv.style.display = 'block'; // AI辅助生成：GLM-5, 2026-03-05
        successDiv.style.background = 'linear-gradient(135deg, #ffeaa7, #fdcb6e)';
        successDiv.style.color = '#856404';
        successDiv.style.borderLeft = '5px solid #f39c12';

        // 3秒后自动隐藏
        setTimeout(() => {
            successDiv.style.display = 'none';
        }, 5000);
    }
}

// 重写处理按钮点击事件
function overrideProcessButton() {
    const processBtn = document.getElementById('processBtn');
    if (processBtn) {
        // 保存原始处理函数引用
        window.originalProcessFiles = processFiles;

        // 移除原有的事件监听器
        processBtn.onclick = null;

        // 添加新的事件监听器
        processBtn.addEventListener('click', function(e) {
            e.preventDefault(); // AI辅助生成：GLM-5, 2026-03-06
            showConfirmationModal();
        });

        console.log("✓ 处理按钮事件已重写");
    }
}

// 显示确认模态框
function showConfirmationModal() {
    const modal = document.getElementById('confirmationModal');
    if (modal) {
        modal.style.display = 'flex';

        // 添加动画效果
        setTimeout(() => {
            const modalContent = modal.querySelector('div');
            if (modalContent) {
                modalContent.style.transform = 'scale(1)';
                modalContent.style.opacity = '1';
            }
        }, 10);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log("DOM加载完成，准备初始化用户提示...");
    setTimeout(initializeUserPrompts, 100);
});

// 导出函数供其他脚本使用（如果需要）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initializeUserPrompts,
        showConfirmationModal,
        showCancelMessage
    };
}