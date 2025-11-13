// const socket = io("http://localhost:5000"); // サーバーURLに合わせる
const socket = io(); // URL 指定しない

let isTyping = false;
let isAppStopped = false;
let longPressTimer = null;
let lastClickTime = 0;

// ページ読み込み時の処理
document.addEventListener("DOMContentLoaded", function () {
    // 起動時ポップアップの処理
    const startupPopup = document.getElementById("startupPopup");
    const startupBtn = document.getElementById("startupBtn");

    startupBtn.addEventListener("click", function () {
        startupPopup.style.display = "none";
        appStart();
    });
});

socket.on("assistant_message", (data) => {
    let message = data.message;
    typeWriterEffect(message);
});

function typeWriterEffect(text, speed = 60, elementId = "serverText") {
    if (isTyping || isAppStopped) return;

    // 表示状態を変更
    const container = document.querySelector(".server-text-area");
    if (container) {
        container.style.display = "block";
    }

    isTyping = true;
    const element = document.getElementById(elementId);
    element.innerHTML = "";
    let i = 0;

    function typeChar() {
        if (i < text.length && !isAppStopped) {
            element.innerHTML = text.substring(0, i + 1) + '<span class="typing-cursor">|</span>';
            i++;
            setTimeout(typeChar, speed);
        } else {
            element.innerHTML = text;
            isTyping = false;
        }
    }
    typeChar();
}

async function appStart() {
    try {
        const response = await fetch("http://localhost:5000/appstart", {
            method: "POST",
        });
        if (response.ok) {
            const data = await response.json();
            console.log(data.status);
            closeControlPanel();
        } else {
            console.error("エラーが発生しました。ステータス:", response.status);
            alert("エラーが発生しました");
        }
    } catch (error) {
        console.error("リクエストに失敗しました:", error);
        alert("リクエストに失敗しました");
    }
}

async function conversationStart() {
    try {
        const response = await fetch("http://localhost:5000/start", {
            method: "POST",
        });
        if (response.ok) {
            const data = await response.json();
            console.log(data.status);
            closeControlPanel();
        } else {
            console.error("エラーが発生しました。ステータス:", response.status);
            alert("エラーが発生しました");
        }
    } catch (error) {
        console.error("リクエストに失敗しました:", error);
        alert("リクエストに失敗しました");
    }
}

async function conversationStop() {
    try {
        const response = await fetch("http://localhost:5000/stop", {
            method: "POST",
        });

        if (response.ok) {
            const data = await response.json();
            console.log(data.status);
            closeControlPanel();
        } else {
            console.error("エラーが発生しました。ステータス:", response.status);
            alert("エラーが発生しました");
        }
    } catch (error) {
        console.error("リクエストに失敗しました:", error);
        alert("リクエストに失敗しました");
    }
}

// コントロールパネル関連の関数
function showControlPanel() {
    document.getElementById("controlPanelOverlay").style.display = "flex";
}

function closeControlPanel() {
    document.getElementById("controlPanelOverlay").style.display = "none";
}

function toggleApp() {
    const toggleButton = document.getElementById("toggleButton");
    const mainContent = document.getElementById("mainContent");

    if (isAppStopped) {
        // 開始
        isAppStopped = false;
        toggleButton.innerHTML = '<i class="fas fa-stop"></i> 停止';
        toggleButton.className = "control-button stop";
        mainContent.classList.remove("app-disabled");
        // 開始時の関数を実行
        conversationStart();
    } else {
        // 停止
        isAppStopped = true;
        toggleButton.innerHTML = '<i class="fas fa-play"></i> 開始';
        toggleButton.className = "control-button start";
        mainContent.classList.add("app-disabled");
        // 終了時の関数を実行
        conversationStop();
    }
    closeControlPanel();
}

async function refreshApp() {
    // window.location.reload();
    try {
        const response = await fetch("http://localhost:5000/restart", {
            method: "POST",
        });
        if (response.ok) {
            const data = await response.json();
            console.log(data.status);
            closeControlPanel();
        } else {
            console.error("エラーが発生しました。ステータス:", response.status);
            alert("エラーが発生しました");
        }
    } catch (error) {
        console.error("リクエストに失敗しました:", error);
        alert("リクエストに失敗しました");
    }
}

async function initPose() {
    try {
        const response = await fetch("http://localhost:5000/initpose", {
            method: "POST",
        });
        if (response.ok) {
            const data = await response.json();
            console.log(data.status);
            closeControlPanel();
        } else {
            console.error("エラーが発生しました。ステータス:", response.status);
            alert("エラーが発生しました");
        }
    } catch (error) {
        console.error("リクエストに失敗しました:", error);
        alert("リクエストに失敗しました");
    }
}

async function homePose() {
    try {
        const response = await fetch("http://localhost:5000/homepose", {
            method: "POST",
        });
        if (response.ok) {
            const data = await response.json();
            console.log(data.status);
            closeControlPanel();
        } else {
            console.error("エラーが発生しました。ステータス:", response.status);
            alert("エラーが発生しました");
        }
    } catch (error) {
        console.error("リクエストに失敗しました:", error);
        alert("リクエストに失敗しました");
    }
}

// ヘッダーのイベントリスナー
document.getElementById("header").addEventListener("mousedown", function (e) {
    longPressTimer = setTimeout(showControlPanel, 1000);
});

document.getElementById("header").addEventListener("mouseup", function (e) {
    if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
    }
});

document.getElementById("header").addEventListener("mouseleave", function (e) {
    if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
    }
});

// タッチイベント
document.getElementById("header").addEventListener(
    "touchstart",
    function (e) {
        e.preventDefault(); // デフォルト動作を防ぐ
        longPressTimer = setTimeout(showControlPanel, 1000);
    },
    { passive: false }
);

document.getElementById("header").addEventListener(
    "touchend",
    function (e) {
        e.preventDefault();
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    },
    { passive: false }
);

// ダブルクリック/ダブルタップ
document.getElementById("header").addEventListener(
    "click",
    function (e) {
        const currentTime = new Date().getTime();
        const timeDiff = currentTime - lastClickTime;

        if (timeDiff < 1000) {
            showControlPanel();
        }

        lastClickTime = currentTime;
    },
    { passive: false }
);

// オーバーレイクリックで閉じる
document.getElementById("controlPanelOverlay").addEventListener("click", function (e) {
    if (e.target === this) {
        closeControlPanel();
    }
});
