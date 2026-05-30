import * as Switch from '@radix-ui/react-switch';
import PropTypes from 'prop-types';

/**
 * ToggleSwitch Component
 * Modern toggle switch using Radix UI Switch primitive
 *
 * @param {boolean} checked - Whether the switch is checked
 * @param {function} onChange - Callback when switch state changes
 * @param {boolean} disabled - Whether the switch is disabled
 * @param {string} size - Size variant: 'sm' or 'md' (default)
 */
const ToggleSwitch = ({ checked, onChange, disabled = false, size = 'md' }) => {
  // Size configurations
  const sizes = {
    sm: {
      container: 'w-9 h-5',
      thumb: 'w-4 h-4',
      translate: checked ? 'translate-x-4' : 'translate-x-0.5'
    },
    md: {
      container: 'w-11 h-6',
      thumb: 'w-5 h-5',
      translate: checked ? 'translate-x-6' : 'translate-x-0.5'
    }
  };

  const sizeConfig = sizes[size] || sizes.md;

  return (
    <Switch.Root
      checked={checked}
      onCheckedChange={onChange}
      disabled={disabled}
      className={`
        relative ${sizeConfig.container} rounded-full transition-all duration-200 ease-in-out
        ${checked ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-300 hover:bg-gray-400'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
        flex items-center
      `}
    >
      <Switch.Thumb
        className={`
          block ${sizeConfig.thumb} bg-white rounded-full shadow-md transition-transform duration-200 ease-in-out
          ${sizeConfig.translate}
        `}
      />
    </Switch.Root>
  );
};

ToggleSwitch.propTypes = {
  checked: PropTypes.bool.isRequired,
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  size: PropTypes.oneOf(['sm', 'md'])
};

export default ToggleSwitch;
