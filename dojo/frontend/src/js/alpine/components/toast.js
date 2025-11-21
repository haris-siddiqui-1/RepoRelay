/**
 * Toast Notification Component
 *
 * Usage:
 * <div x-data="toast">
 *   <button @click="show('Success message', 'success')">Show Toast</button>
 * </div>
 */

export default () => ({
  visible: false,
  message: '',
  type: 'info', // info, success, warning, error
  duration: 3000,

  show(message, type = 'info', duration = 3000) {
    this.message = message;
    this.type = type;
    this.duration = duration;
    this.visible = true;

    // Auto-hide after duration
    setTimeout(() => {
      this.hide();
    }, duration);
  },

  hide() {
    this.visible = false;
  },

  getTypeClasses() {
    const classes = {
      info: 'bg-blue-50 dark:bg-blue-900/30 border-blue-400 text-blue-700 dark:text-blue-300',
      success: 'bg-green-50 dark:bg-green-900/30 border-green-400 text-green-700 dark:text-green-300',
      warning: 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-400 text-yellow-700 dark:text-yellow-300',
      error: 'bg-red-50 dark:bg-red-900/30 border-red-400 text-red-700 dark:text-red-300',
    };
    return classes[this.type] || classes.info;
  },
});
