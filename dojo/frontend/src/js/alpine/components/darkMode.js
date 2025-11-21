/**
 * Dark Mode Component
 *
 * Usage:
 * <div x-data="darkMode">
 *   <button @click="toggle">Toggle Dark Mode</button>
 * </div>
 */

export default () => ({
  dark: false,

  init() {
    // Check for saved preference or system preference
    this.dark = localStorage.getItem('darkMode') === 'true' ||
                (!localStorage.getItem('darkMode') && window.matchMedia('(prefers-color-scheme: dark)').matches);

    // Apply initial state
    this.updateDOM();

    // Watch for system preference changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem('darkMode')) {
        this.dark = e.matches;
        this.updateDOM();
      }
    });
  },

  toggle() {
    this.dark = !this.dark;
    this.updateDOM();
    localStorage.setItem('darkMode', this.dark.toString());
  },

  updateDOM() {
    if (this.dark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  },
});
