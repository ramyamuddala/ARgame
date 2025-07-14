// static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Element Selectors ---
    const startBtn = document.getElementById('start-btn');
    const resetBtn = document.getElementById('reset-btn');
    const nextLevelBtn = document.getElementById('next-level-btn');
    const levelDisplay = document.getElementById('level-display');
    
    const aboutBtn = document.getElementById('about-btn');
    const aboutModal = document.getElementById('about-modal');
    const closeModalBtn = document.querySelector('.close-btn');

    let statusInterval;

    // --- UI State Management ---
    function updateUIForState(state, level, totalLevels) {
        levelDisplay.textContent = `Level ${level} / ${totalLevels}`;

        startBtn.style.display = 'none';
        nextLevelBtn.style.display = 'none';

        switch (state) {
            case 'idle':
                startBtn.style.display = 'inline-block';
                break;
            case 'running':
                // No primary action button visible
                break;
            case 'level_complete':
                nextLevelBtn.style.display = 'inline-block';
                break;
            case 'game_over':
                levelDisplay.textContent = "You Win!";
                levelDisplay.style.backgroundColor = '#009688'; // Success color
                break;
        }
    }

    // --- Game Status Polling ---
    async function checkStatus() {
        try {
            const response = await fetch('/status');
            const data = await response.json();
            updateUIForState(data.gameState, data.level, data.totalLevels);
        } catch (error) {
            console.error('Error fetching status:', error);
        }
    }

    // --- Event Listeners ---
    startBtn.addEventListener('click', async () => {
        try {
            await fetch('/start', { method: 'POST' });
            console.log('Game started');
        } catch (error) {
            console.error('Error starting game:', error);
        }
    });

    resetBtn.addEventListener('click', async () => {
        try {
            await fetch('/reset', { method: 'POST' });
            levelDisplay.style.backgroundColor = 'var(--primary-color)'; // Reset color
            console.log('Game reset');
        } catch (error) {
            console.error('Error resetting game:', error);
        }
    });

    nextLevelBtn.addEventListener('click', async () => {
        try {
            await fetch('/next_level', { method: 'POST' });
            console.log('Loading next level');
        } catch (error) {
            console.error('Error loading next level:', error);
        }
    });

    // --- Modal Logic ---
    aboutBtn.addEventListener('click', () => {
        aboutModal.style.display = 'flex';
    });

    closeModalBtn.addEventListener('click', () => {
        aboutModal.style.display = 'none';
    });

    window.addEventListener('click', (event) => {
        if (event.target === aboutModal) {
            aboutModal.style.display = 'none';
        }
    });

    // --- Initialization ---
    function init() {
        statusInterval = setInterval(checkStatus, 1000); // Poll every second
        checkStatus(); // Initial check
    }

    init();
});
