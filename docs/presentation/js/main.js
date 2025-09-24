document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling for navigation links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                const offsetTop = target.offsetTop - 70; // Account for fixed navbar
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });

    // Add scroll effect to navbar and progress indicator
    const navbar = document.querySelector('.navbar');
    const progressBar = document.querySelector('.progress-bar');

    window.addEventListener('scroll', function() {
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const scrollPercent = (scrollTop / docHeight) * 100;

        // Update progress bar
        if (progressBar) {
            progressBar.style.width = scrollPercent + '%';
        }

        // Keep navbar always visible, just change background opacity
        if (scrollTop > 50) {
            navbar.style.background = 'rgba(255, 255, 255, 0.98)';
            navbar.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.1)';
        } else {
            navbar.style.background = 'rgba(255, 255, 255, 0.95)';
            navbar.style.boxShadow = 'none';
        }
    });

    // Intersection Observer for animations
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe all cards and sections for animation
    document.querySelectorAll('.arch-card, .security-card, .metric-card, .usecase-card, .achievement-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });

    // Counter animation for metrics
    function animateCounter(element, target, duration = 2000) {
        let start = 0;
        const increment = target / (duration / 16);
        const timer = setInterval(() => {
            start += increment;
            if (start >= target) {
                element.textContent = target;
                clearInterval(timer);
            } else {
                element.textContent = Math.floor(start);
            }
        }, 16);
    }

    // Animate counters when metrics section comes into view
    const metricsObserver = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const metricValues = entry.target.querySelectorAll('.metric-value');
                metricValues.forEach(value => {
                    const text = value.textContent;
                    const number = parseInt(text.replace(/\D/g, ''));
                    if (number && !isNaN(number)) {
                        value.textContent = '0';
                        setTimeout(() => {
                            animateCounter(value, number);
                        }, 200);
                    }
                });
                metricsObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    const metricsSection = document.querySelector('#efficiency');
    if (metricsSection) {
        metricsObserver.observe(metricsSection);
    }

    // Add ripple effect to cards (excluding arch-cards which have flip functionality)
    document.querySelectorAll('.security-card, .usecase-card, .achievement-card').forEach(card => {
        card.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;

            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');

            this.appendChild(ripple);

            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });

    // Add CSS for ripple effect
    const style = document.createElement('style');
    style.textContent = `
        .security-card, .usecase-card, .achievement-card {
            position: relative;
            overflow: hidden;
            cursor: pointer;
        }

        .arch-card {
            position: relative;
            overflow: hidden;
            cursor: pointer;
        }

        .ripple {
            position: absolute;
            border-radius: 50%;
            background: rgba(30, 64, 175, 0.1);
            transform: scale(0);
            animation: ripple-animation 0.6s linear;
            pointer-events: none;
        }

        @keyframes ripple-animation {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);

    // Performance monitoring (simulated for demo)
    function updatePerformanceMetrics() {
        const responseTimeElements = document.querySelectorAll('.metric-value');
        responseTimeElements.forEach(element => {
            if (element.textContent.includes('ms')) {
                // Simulate real-time response time updates
                const baseTime = 450;
                const variation = Math.random() * 100;
                const newTime = Math.floor(baseTime + variation);
                element.textContent = `<${newTime}ms`;
            }
        });
    }

    // Update metrics every 30 seconds for demo purposes
    setInterval(updatePerformanceMetrics, 30000);

    // Add click listeners to architecture cards for flip functionality
    console.log('Setting up flip cards');
    const archCards = document.querySelectorAll('.arch-card');
    console.log('Found arch cards:', archCards.length);

    archCards.forEach((card, index) => {
        card.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            this.classList.toggle('show-tools');
        });
    });
});
