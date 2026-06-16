document.addEventListener('DOMContentLoaded', () => {
    // Node counter randomizer
    setInterval(() => {
        const count = Math.floor(Math.random() * 5) + 12;
        document.getElementById('node-count').innerText = count;
    }, 5000);

    // Boot Sequence Animation
    const bootLines = [
        "ZERONET BIOS v1.0.0",
        "COPYRIGHT (C) 2026 ZERONET FOUNDATION",
        "CHECKING MEMORY... OK",
        "INITIALIZING NETWORK INTERFACES... OK",
        "STARTING MDNS DISCOVERY SERVICE... OK",
        "GENERATING ECDH KEYPAIR (SECP256R1)... OK",
        "AWAITING PEER CONNECTIONS..."
    ];

    const bootContainer = document.getElementById('boot-text');
    let lineIdx = 0;

    function typeLine() {
        if (lineIdx < bootLines.length) {
            const div = document.createElement('div');
            div.className = 'log-line';
            div.innerText = bootLines[lineIdx];
            
            if (bootLines[lineIdx].includes('OK')) {
                div.innerHTML = bootLines[lineIdx].replace('OK', '<span class="ok">OK</span>');
            }

            bootContainer.appendChild(div);
            lineIdx++;
            setTimeout(typeLine, Math.random() * 400 + 100);
        }
    }
    
    setTimeout(typeLine, 500);

    // Interactive Demo
    const chatInput = document.getElementById('demo-input');
    const chatLog = document.getElementById('demo-messages');
    const cryptoOut = document.getElementById('crypto-output');

    // Simple pseudo-random hex string generator
    function generateHex(length) {
        let result = '';
        const characters = '0123456789abcdef';
        for (let i = 0; i < length; i++) {
            result += characters.charAt(Math.floor(Math.random() * characters.length));
        }
        return result;
    }

    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && this.value.trim() !== '') {
            const text = this.value.trim();
            this.value = '';

            // Add sent message
            const msgDiv = document.createElement('div');
            msgDiv.className = 'msg out';
            msgDiv.innerHTML = `<span class="sender">&lt;YOU&gt;</span> ${text}`;
            chatLog.appendChild(msgDiv);
            
            // Scroll to bottom
            chatLog.scrollTop = chatLog.scrollHeight;

            // Generate fake cipher output
            const ciphertext = `gAAAAABm0K4xN2Y3ZGE4${generateHex(64)}=`;
            const header = `[META: 124B][PAYLOAD: ${ciphertext.length}B]`;
            cryptoOut.innerText = `TRANSMITTING:\n${header}\n${ciphertext}`;
            cryptoOut.style.color = 'var(--highlight)';

            // Simulate Alice typing reply
            setTimeout(() => {
                cryptoOut.innerText = `RECEIVING DATA...`;
                cryptoOut.style.color = 'var(--dim-text)';
            }, 800);

            setTimeout(() => {
                const incomingCipher = `gAAAAABq9P2y${generateHex(64)}=`;
                cryptoOut.innerText = `RECEIVED:\n[META: 118B][PAYLOAD: ${incomingCipher.length}B]\n${incomingCipher}`;
                cryptoOut.style.color = 'var(--text-color)';
                
                const replyDiv = document.createElement('div');
                replyDiv.className = 'msg in';
                const replies = [
                    "ROGER THAT.",
                    "AFFIRMATIVE.",
                    "DATA RECEIVED SECURELY.",
                    "ZERO TRACES LEFT."
                ];
                const reply = replies[Math.floor(Math.random() * replies.length)];
                replyDiv.innerHTML = `<span class="sender">&lt;ALICE&gt;</span> ${reply}`;
                chatLog.appendChild(replyDiv);
                chatLog.scrollTop = chatLog.scrollHeight;
            }, 2000);
        }
    });

    // Auto-focus input when clicking terminal area
    document.querySelector('.demo-chat').addEventListener('click', () => {
        chatInput.focus();
    });
});
