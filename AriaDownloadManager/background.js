// 默认配置（应与 Python utils.py 中的配置一致）
const DEFAULT_CONFIG = {
    rpcUrl: "http://localhost:6800/jsonrpc",
    secret: "", // 如果你在 utils.py 设置了密码，请在此填写
    enabled: true
};

// 全局错误处理
self.addEventListener('error', (event) => {
    console.error('Service Worker 全局错误:', event.error);
});

self.addEventListener('unhandledrejection', (event) => {
    console.error('未处理的 Promise 拒绝:', event.reason);
    event.preventDefault(); // 防止错误被报告到控制台
});

// 监听下载事件
chrome.downloads.onCreated.addListener(async (downloadItem) => {
    const config = await chrome.storage.local.get(DEFAULT_CONFIG);
    
    if (!config.enabled) return;

    // 排除已经由本插件处理的下载（防止死循环）
    if (downloadItem.byExtensionId === chrome.runtime.id) return;

    // 跳过图片下载（通常不需要接管）
    const mimeType = downloadItem.mime || '';
    if (mimeType.startsWith('image/')) {
        return;
    }

    // 拦截下载并取消浏览器自带下载
    try {
        await chrome.downloads.cancel(downloadItem.id);
    } catch (error) {
        console.warn("取消下载失败:", error);
    }

    // 延迟删除下载记录，确保操作完成
    setTimeout(async () => {
        try {
            await chrome.downloads.erase({ id: downloadItem.id });
        } catch (error) {
            // 忽略删除失败的错误，这通常不影响功能
            console.warn("删除下载记录失败:", error);
        }
    }, 100);

    // 获取完整的下载信息（包括 cookies 和请求头）
    try {
        const info = await getDownloadInfo(downloadItem);
        await sendToAria2(info.url, info.options, config);
    } catch (error) {
        console.error("获取下载信息失败:", error);
        showNotification("接管失败", "无法获取下载信息: " + (error.message || "未知错误"));
    }
});

/**
 * 获取下载信息，包括最终 URL、cookies 和请求头
 * @param {chrome.downloads.DownloadItem} downloadItem 
 * @returns {Promise<{url: string, options: object}>}
 */
async function getDownloadInfo(downloadItem) {
    // 优先使用 Chrome 解析过的 finalUrl (Chrome 54+)
    let finalUrl = downloadItem.finalUrl || downloadItem.url;
    const options = {};
    let filename = null;

    // 判断是否为二进制文件下载（非 HTML）
    const isBinary = downloadItem.mime && !downloadItem.mime.includes('text/html') && !downloadItem.mime.includes('application/xhtml');

    // 尝试获取响应头以提取文件名 (Content-Disposition)
    let responseHeaders = null;
    try {
        // 使用 HEAD 请求获取头部信息
        const headResult = await quickHeadRequest(finalUrl, downloadItem.referrer);
        const headContentType = headResult.headers ? (headResult.headers.get('content-type') || '') : '';
        
        // 如果原下载是文件，但 HEAD 请求返回了 HTML，说明直接请求被拦截或重定向到了页面，忽略该结果
        if (isBinary && headContentType.includes('text/html')) {
            console.warn("HEAD 请求返回了 HTML，忽略该结果，使用原始 URL");
        } else {
            responseHeaders = headResult.headers;
            // 如果 URL 发生了变化且不是 HTML，更新 finalUrl
            if (headResult.url && headResult.url !== finalUrl && !headContentType.includes('text/html')) {
                finalUrl = headResult.url;
            }
        }
    } catch (error) {
        console.warn("HEAD 请求失败，将使用原始信息:", error);
    }

    // 1. 从 Content-Disposition 头提取文件名 (修复乱码问题)
    if (responseHeaders) {
        const contentDisposition = responseHeaders.get('content-disposition');
        if (contentDisposition) {
            filename = parseContentDisposition(contentDisposition);
        }
    }

    // 2. 如果没有文件名，尝试从 URL 提取
    if (!filename) {
        try {
            const urlObj = new URL(finalUrl);
            const pathname = urlObj.pathname;
            // 解码 URL 路径中的文件名
            const urlFilename = decodeURIComponent(pathname.split('/').pop());
            if (urlFilename && urlFilename.includes('.')) {
                filename = urlFilename;
            }
        } catch (e) {}
    }

    // 3. 使用 downloadItem.filename (通常是绝对路径，需提取文件名)
    if (!filename && downloadItem.filename) {
        try {
            const basename = downloadItem.filename.replace(/^.*[\\\/]/, '');
            if (basename) filename = basename;
        } catch (e) {}
    }

    // 4. 设置文件名 (清理非法字符)
    if (filename) {
        filename = filename.replace(/[<>:"|?*]/g, '_');
        options.out = filename;
    }

    // 5. 获取 cookies
    try {
        const cookies = await getCookiesForUrl(finalUrl);
        if (cookies && cookies.length > 0) {
            options.header = options.header || [];
            const cookieString = cookies.map(c => `${c.name}=${c.value}`).join('; ');
            options.header.push(`Cookie: ${cookieString}`);
        }
    } catch (error) {
        console.warn("获取 cookies 失败:", error);
    }

    // 6. 添加必要的请求头
    options.header = options.header || [];
    
    // User-Agent
    if (!options.header.some(h => h.startsWith('User-Agent:'))) {
        const userAgent = navigator.userAgent;
        options.header.push(`User-Agent: ${userAgent}`);
    }
    
    // Referer
    if (downloadItem.referrer && !options.header.some(h => h.startsWith('Referer:'))) {
        options.header.push(`Referer: ${downloadItem.referrer}`);
    }

    return {
        url: finalUrl,
        options: options
    };
}

/**
 * 解析 Content-Disposition 头，正确处理 UTF-8 编码
 * @param {string} header 
 * @returns {string|null}
 */
function parseContentDisposition(header) {
    if (!header) return null;
    
    // 优先匹配 RFC 5987 格式: filename*=UTF-8''encoded_value
    const rfcMatch = header.match(/filename\*=UTF-8''([^;]+)/i);
    if (rfcMatch && rfcMatch[1]) {
        try {
            return decodeURIComponent(rfcMatch[1]);
        } catch (e) {
            console.warn("解码 filename* 失败:", e);
        }
    }
    
    // 匹配标准格式: filename="value" 或 filename=value
    const stdMatch = header.match(/filename=["']?([^"';]+)["']?/i);
    if (stdMatch && stdMatch[1]) {
        try {
            return decodeURIComponent(stdMatch[1]);
        } catch (e) {
            return stdMatch[1];
        }
    }
    
    return null;
}

/**
 * 快速 HEAD 请求获取 headers
 */
async function quickHeadRequest(url, referrer) {
    const res = await fetch(url, {
        method: 'HEAD',
        referrer: referrer || undefined,
        credentials: 'include' // 携带 cookies
    });
    return { url: res.url, headers: res.headers };
}

/**
 * 获取指定 URL 的所有 cookies
 * @param {string} url 
 * @returns {Promise<chrome.cookies.Cookie[]>}
 */
async function getCookiesForUrl(url) {
    try {
        const urlObj = new URL(url);
        const hostname = urlObj.hostname;
        
        // 尝试多种方式获取 cookies
        let cookies = [];
        
        // 方法1: 使用完整域名
        try {
            cookies = await chrome.cookies.getAll({ url: url });
        } catch (e) {
            // 方法2: 使用域名（不带协议）
            try {
                cookies = await chrome.cookies.getAll({ domain: hostname });
            } catch (e2) {
                // 方法3: 尝试主域名（处理子域名）
                try {
                    const mainDomain = hostname.split('.').slice(-2).join('.');
                    if (mainDomain !== hostname) {
                        cookies = await chrome.cookies.getAll({ domain: mainDomain });
                    }
                } catch (e3) {
                    console.warn("无法获取 cookies:", e3);
                }
            }
        }
        
        return cookies || [];
    } catch (error) {
        console.error("获取 cookies 时出错:", error);
        return [];
    }
}

/**
 * 发送下载任务到 Aria2
 * @param {string} url 
 * @param {object} options 
 * @param {object} config 
 */
async function sendToAria2(url, options, config) {
    const params = [
        config.secret ? `token:${config.secret}` : null,
        [url],
        options
    ].filter(p => p !== null);

    const rpcData = {
        jsonrpc: "2.0",
        id: "pyMediaExtension",
        method: "aria2.addUri",
        params: params
    };

    try {
        const response = await fetch(config.rpcUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(rpcData)
        });
        
        const result = await response.json();
        if (result.result) {
            showNotification("下载已接管", "任务已成功发送至 pyMedia 下载管理器");
        } else if (result.error) {
            throw new Error(result.error.message || "未知错误");
        }
    } catch (error) {
        showNotification("接管失败", "无法连接到下载管理器，请检查程序是否启动");
        console.error("Aria2 RPC Error:", error);
    }
}

async function showNotification(title, message) {
    // 确保所有必需的属性都存在且有效
    if (!title || !message) {
        console.error("通知缺少必需的属性:", { title, message });
        return;
    }

    // 确保 title 和 message 是字符串，且不为空
    const notificationTitle = String(title || '通知').trim();
    const notificationMessage = String(message || '').trim();
    
    if (!notificationTitle || !notificationMessage) {
        console.error("通知标题或消息为空");
        return;
    }

    // 获取扩展图标 URL
    // 注意：即使文件不存在，getURL 也会返回一个有效的 URL 格式
    // Chrome 会在图标文件不存在时显示默认图标
    let iconUrl = chrome.runtime.getURL('icon.png');
    
    // 确保 iconUrl 不为空（虽然理论上不会为空）
    if (!iconUrl) {
        // 如果 getURL 返回空，使用扩展 ID 构造 URL
        iconUrl = `chrome-extension://${chrome.runtime.id}/icon.png`;
    }

    // 创建通知选项对象，确保包含所有必需属性
    // Chrome API 要求：type, iconUrl, title, message 都是必需的
    const notificationOptions = {
        type: 'basic',
        iconUrl: iconUrl,
        title: notificationTitle,
        message: notificationMessage,
        priority: 2
    };

    // 使用回调方式创建通知，以便更好地处理 lastError
    chrome.notifications.create(notificationOptions, (notificationId) => {
        // 检查是否有运行时错误
        if (chrome.runtime.lastError) {
            console.error("通知创建时出现运行时错误:", chrome.runtime.lastError.message);
            // 即使有错误，也输出到控制台
            console.log(`[${notificationTitle}] ${notificationMessage}`);
            return;
        }
        
        if (notificationId) {
            console.log("通知已创建:", notificationId);
        } else {
            console.error("通知创建失败: 未返回通知 ID");
            console.log(`[${notificationTitle}] ${notificationMessage}`);
        }
    });
}