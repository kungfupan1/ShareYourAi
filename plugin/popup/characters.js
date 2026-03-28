/**
 * 小人动效控制器 - 完全复刻原版
 */
class CharacterAnimator {
  constructor() {
    this.charactersContainer = document.getElementById('charactersContainer');
    this.characters = document.querySelectorAll('.character');
    this.charBodies = [
      document.querySelector('.char-purple .char-body'),
      document.querySelector('.char-black .char-body'),
      document.querySelector('.char-yellow .char-body'),
      document.querySelector('.char-orange .char-body')
    ];
    this.eyeContainers = document.querySelectorAll('.eyes');
    this.eyePupils = document.querySelectorAll('.eye-pupil');
    this.bigEyes = document.querySelectorAll('.eye-big');
    this.smallEyes = document.querySelectorAll('.eye-small');
    this.mouth = document.querySelector('.mouth');

    this.isPasswordVisible = false;
    this.isPeeking = false;
    this.maxRotate = 15;
    this.minRotate = -15;
    this.isInitialized = false;

    // 小人身体宽度，用于限制眼睛最大位移
    this.bodyWidths = [30, 25, 30, 50]; // 紫、黑、黄、橙

    // 大眼睛尺寸（白色眼框）
    this.bigEyeSize = 6; // 6px
    // 黑瞳尺寸
    this.pupilSize = 2; // 2px
    // 黑瞳最大偏移量（不能超出白眼框）
    this.maxPupilOffset = (this.bigEyeSize - this.pupilSize) / 2; // 2px

    this.init();
  }

  init() {
    // 设置原始高度 CSS 变量
    this.charBodies[0]?.style.setProperty('--original-height', '130px');
    this.charBodies[1]?.style.setProperty('--original-height', '110px');
    this.charBodies[2]?.style.setProperty('--original-height', '90px');
    this.charBodies[3]?.style.setProperty('--original-height', '65px');

    // 触发探出头动画
    this.triggerPopUpAnimation();

    // 延迟启动其他动画（等探出头动画完成）
    setTimeout(() => {
      this.isInitialized = true;
      this.initBlinkAnimation();
      this.bindMouseFollow();
      this.bindInputEvents();
      this.bindPasswordToggle();
    }, 1400);
  }

  // 探出头动画
  triggerPopUpAnimation() {
    // 第一个：紫色（0s）
    // 第二批：黑色+黄色（0.25s）一起
    // 第三个：橘色（0.75s，比黑色慢0.5s）
    const delays = [0, 250, 250, 750];
    const duration = 500; // 动画时长

    this.characters.forEach((char, index) => {
      setTimeout(() => {
        char.classList.add('pop-up');
      }, delays[index]);

      // 动画结束后清除 animation，让 transform 可以被 JS 控制
      setTimeout(() => {
        const body = this.charBodies[index];
        if (body) {
          body.style.animation = 'none';
          body.style.transform = 'scaleY(1)';
        }
      }, delays[index] + duration + 100);
    });
  }
  initBlinkAnimation() {
    // 紫色小人：慢频率（6-8秒），每次眨1次
    this.blinkIntervals = [];
    this.blinkIntervals.push(
      setInterval(() => {
        this.blinkMultipleTimes(document.querySelectorAll('.char-purple .eye-big'), 1);
      }, 6000 + Math.random() * 2000)
    );

    // 黑色小人：中频率（4-5秒），每次眨2次
    this.blinkIntervals.push(
      setInterval(() => {
        this.blinkMultipleTimes(document.querySelectorAll('.char-black .eye-big'), 2);
      }, 4000 + Math.random() * 1000)
    );

    // 黄色小人：快频率（2-3秒），每次眨3次
    this.blinkIntervals.push(
      setInterval(() => {
        this.blinkMultipleTimes(document.querySelectorAll('.char-yellow .eye-small'), 3);
      }, 2000 + Math.random() * 1000)
    );

    // 橙色小人：极慢频率（8-10秒），每次眨1次
    this.blinkIntervals.push(
      setInterval(() => {
        this.blinkMultipleTimes(document.querySelectorAll('.char-orange .eye-small'), 1);
      }, 8000 + Math.random() * 2000)
    );
  }

  // 单个眨眼动作
  blinkEye(eyes, callback) {
    eyes.forEach(eye => {
      eye.style.height = '1px';
      setTimeout(() => {
        // 适配偷窥状态的眼睛尺寸
        if (eye.closest('.char-yellow')) {
          eye.style.height = this.isPeeking ? '5px' : '4px';
        } else if (eye.closest('.char-orange')) {
          eye.style.height = '4px';
        } else {
          eye.style.height = this.isPeeking ? (eye.classList.contains('eye-big') ? '8px' : '4px') : (eye.classList.contains('eye-big') ? '6px' : '4px');
        }
        if (callback) callback();
      }, 100 + Math.random() * 50);
    });
  }

  // 多次眨眼逻辑
  blinkMultipleTimes(eyes, times) {
    let currentBlink = 0;
    const doBlink = () => {
      this.blinkEye(eyes, () => {
        currentBlink++;
        if (currentBlink < times) {
          setTimeout(doBlink, 200 + Math.random() * 100);
        }
      });
    };
    doBlink();
  }

  // 3. 偷窥高频眨眼
  peekBlink() {
    // 密码显示状态下不执行偷窥眨眼
    if (this.isPasswordVisible) return;

    let blinkCount = 0;
    const blinkInterval = setInterval(() => {
      this.bigEyes.forEach(eye => {
        eye.style.height = '1px';
        setTimeout(() => {
          eye.style.height = '8px';
        }, 80);
      });
      document.querySelectorAll('.char-yellow .eye-small').forEach(eye => {
        eye.style.height = '1px';
        setTimeout(() => {
          eye.style.height = '5px';
        }, 80);
      });
      document.querySelectorAll('.char-orange .eye-small').forEach(eye => {
        eye.style.height = '1px';
        setTimeout(() => {
          eye.style.height = '4px';
        }, 80);
      });
      blinkCount++;
      if (blinkCount >= 3) clearInterval(blinkInterval);
    }, 200);
  }

  // 4. 切换偷窥状态
  togglePeeking(active) {
    // 密码显示状态下禁用偷窥动作
    if (this.isPasswordVisible) {
      this.isPeeking = false;
      return;
    }

    this.isPeeking = active;
    this.characters.forEach(char => {
      char.classList.toggle('peeking', active);
    });
    if (active) {
      this.peekBlink();
    } else {
      this.charBodies.forEach(body => {
        body.style.transform = '';
      });
    }
  }

  // 5. 杆子摆动+眼睛跟随逻辑
  updateCharacterSwing(mouseX, mouseY) {
    if (!this.charactersContainer) return;

    const containerRect = this.charactersContainer.getBoundingClientRect();
    const containerCenterX = containerRect.left + containerRect.width / 2;
    const containerCenterY = containerRect.top + containerRect.height / 2;

    const mouseOffsetX = (mouseX - containerCenterX) / containerRect.width * 100;
    const mouseOffsetY = (mouseY - containerCenterY) / containerRect.height * 100;

    const swingAngle = this.isPasswordVisible
      ? -12  // 密码显示时身体更往左倾
      : Math.max(this.minRotate, Math.min(this.maxRotate, mouseOffsetX / 5));

    // 小人身体摆动
    if (!this.isPeeking || this.isPasswordVisible) {
      this.charBodies.forEach((body, index) => {
        const swingCoeff = 1.5 - (index * 0.25);
        body.style.transform = `rotate(${swingAngle * swingCoeff}deg)`;
      });
    }

    // 眼睛+黑瞳联动
    this.eyeContainers.forEach((eyes, index) => {
      let offsetX, offsetY;
      if (this.isPasswordVisible) {
        offsetX = -4;  // 更往左
        offsetY = -3;  // 更往上
      } else {
        offsetX = swingAngle / 1.8;
        offsetY = mouseOffsetY / 6;
      }

      // 限制眼睛位移范围：最多移动小人身体宽度的一半
      const maxOffset = this.bodyWidths[index] / 2;
      const clampedOffsetX = Math.max(-maxOffset, Math.min(maxOffset, offsetX));
      const clampedOffsetY = Math.max(-maxOffset, Math.min(maxOffset, offsetY));

      // 非偷窥状态下更新眼睛位置
      if (!this.isPeeking || this.isPasswordVisible) {
        // 矮个子眼睛（纯黑小眼睛）
        eyes.querySelectorAll('.eye-small').forEach(eye => {
          eye.style.transform = `translate(${clampedOffsetX}px, ${clampedOffsetY}px)`;
        });

        // 高个子眼睛（白色大眼睛）
        eyes.querySelectorAll('.eye-big').forEach(eye => {
          eye.style.transform = `translate(${clampedOffsetX}px, ${clampedOffsetY}px)`;
        });

        // 黑瞳转动 - 限制在白眼框内，不能离开
        // 只有紫色和黑色小人有黑瞳
        const isBigEyeCharacter = index === 0 || index === 1; // 紫色或黑色
        if (isBigEyeCharacter) {
          // 黑瞳偏移量限制在白眼框内
          const pupilOffsetX = Math.max(-this.maxPupilOffset, Math.min(this.maxPupilOffset, clampedOffsetX * 0.4));
          const pupilOffsetY = Math.max(-this.maxPupilOffset, Math.min(this.maxPupilOffset, clampedOffsetY * 0.4));
          this.eyePupils.forEach(pupil => {
            pupil.style.transform = `translate(-50%, -50%) translate(${pupilOffsetX}px, ${pupilOffsetY}px)`;
          });
        }

        // 黄色小人嘴巴联动 - 幅度为眼睛的90%
        if (this.mouth && index === 2) {
          const mouthOffsetX = clampedOffsetX * 0.9;
          const mouthOffsetY = clampedOffsetY * 0.9;
          const mouthRotate = clampedOffsetX * 0.09;
          this.mouth.style.transform = `translateX(-50%) translateX(${mouthOffsetX}px) translateY(${mouthOffsetY}px) rotate(${mouthRotate}deg)`;
        }
      }
    });
  }

  // 6. 监听鼠标移动
  bindMouseFollow() {
    document.addEventListener('mousemove', (e) => {
      this.updateCharacterSwing(e.clientX, e.clientY);
    });
  }

  // 7. 密码显隐逻辑
  bindPasswordToggle() {
    const toggleBtn = document.getElementById('togglePassword');
    const passwordInput = document.getElementById('login-password');

    if (toggleBtn && passwordInput) {
      toggleBtn.addEventListener('click', () => {
        this.isPasswordVisible = !this.isPasswordVisible;
        passwordInput.type = this.isPasswordVisible ? 'text' : 'password';

        // 切换图标
        toggleBtn.textContent = this.isPasswordVisible ? '🙈' : '👁';

        // 密码显示时：退出偷窥状态，小人恢复正常待机
        if (this.isPasswordVisible) {
          this.isPeeking = false;
          this.characters.forEach(char => {
            char.classList.remove('peeking');
          });
        }

        // 触发一次眼睛位置更新
        this.updateCharacterSwing(window.innerWidth / 2, window.innerHeight / 2);
      });
    }
  }

  // 8. 监听输入框聚焦/失焦
  bindInputEvents() {
    const inputs = document.querySelectorAll('input[type="text"], input[type="email"], input[type="password"]');
    inputs.forEach(input => {
      input.addEventListener('focus', () => this.togglePeeking(true));
      input.addEventListener('blur', () => this.togglePeeking(false));
    });
  }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
  // 初始化小人动效
  new CharacterAnimator();

  // 初始化鼠标位置
  setTimeout(() => {
    const event = new MouseEvent('mousemove', {
      clientX: window.innerWidth / 2,
      clientY: window.innerHeight / 2
    });
    document.dispatchEvent(event);
  }, 1500);
});