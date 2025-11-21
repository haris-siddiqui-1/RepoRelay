/**
 * Dropdown Component
 *
 * Usage:
 * <div x-data="dropdown">
 *   <button @click="toggle">Menu</button>
 *   <div x-show="open" x-transition @click.away="close">
 *     Dropdown content
 *   </div>
 * </div>
 */

export default () => ({
  open: false,

  toggle() {
    this.open = !this.open;
  },

  close() {
    this.open = false;
  },

  // Keyboard navigation
  handleKeydown(event) {
    if (event.key === 'Escape') {
      this.close();
    }
  },
});
