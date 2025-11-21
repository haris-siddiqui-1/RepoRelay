/**
 * Modal Component
 *
 * Usage:
 * <div x-data="modal">
 *   <button @click="open">Open Modal</button>
 *   <div x-show="isOpen" x-transition class="modal-backdrop">
 *     <div class="modal-content">
 *       <button @click="close">Close</button>
 *       Modal content
 *     </div>
 *   </div>
 * </div>
 */

export default () => ({
  isOpen: false,

  open() {
    this.isOpen = true;
    document.body.style.overflow = 'hidden'; // Prevent body scroll
  },

  close() {
    this.isOpen = false;
    document.body.style.overflow = ''; // Restore body scroll
  },

  // Close on Escape key
  handleKeydown(event) {
    if (event.key === 'Escape' && this.isOpen) {
      this.close();
    }
  },

  init() {
    document.addEventListener('keydown', this.handleKeydown.bind(this));
  },

  destroy() {
    document.removeEventListener('keydown', this.handleKeydown);
  },
});
