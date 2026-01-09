/**
 * popup.js
 * 处理插件弹窗的交互逻辑，符合 Chrome 扩展 CSP 规范
 */

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('toggleBtn');
    const txt = document.getElementById('statusTxt');

    // 初始化状态
    chrome.storage.local.get({ enabled: true }, (res) => {
        updateUI(res.enabled);
    });

    // 绑定点击事件
    btn.addEventListener('click', () => {
        chrome.storage.local.get({ enabled: true }, (res) => {
            const newState = !res.enabled;
            chrome.storage.local.set({ enabled: newState }, () => {
                updateUI(newState);
            });
        });
    });

    /**
     * 更新 UI 显示状态
     * @param {boolean} enabled 
     */
    function updateUI(enabled) {
        txt.innerText = enabled ? "开启" : "关闭";
        txt.style.color = enabled ? "green" : "red";
        btn.innerText = enabled ? "关闭接管" : "开启接管";
    }
});