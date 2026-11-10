<?php
/**
 * Loads the free shipping bar into the Cart and Checkout blocks.
 *
 * @package Ombra\StoreTools
 */

namespace Ombra\StoreTools;

use Automattic\WooCommerce\Blocks\Integrations\IntegrationInterface;

defined( 'ABSPATH' ) || exit;

/**
 * Integration for the Cart and Checkout blocks (registered on their registration hooks).
 */
class Blocks_Integration implements IntegrationInterface {

	const NAME   = 'ombra-store-tools';
	const HANDLE = 'ombra-store-tools-cart-checkout';

	/**
	 * Integration name.
	 *
	 * @return string
	 */
	public function get_name() {
		return self::NAME;
	}

	/**
	 * Register the script and its stylesheet.
	 */
	public function initialize() {
		$base = plugin_dir_url( FILE );
		wp_register_script(
			self::HANDLE,
			$base . 'assets/js/cart-checkout.js',
			array( 'wp-element', 'wp-plugins', 'wc-blocks-checkout' ),
			VERSION,
			array( 'in_footer' => true )
		);
		wp_register_style( self::HANDLE, $base . 'blocks/free-shipping-progress/style.css', array(), VERSION );
		wp_enqueue_style( self::HANDLE );
	}

	/**
	 * Scripts for the front end.
	 *
	 * @return string[]
	 */
	public function get_script_handles() {
		return array( self::HANDLE );
	}

	/**
	 * Scripts for the editor (none: the bar only shows real cart data).
	 *
	 * @return string[]
	 */
	public function get_editor_script_handles() {
		return array();
	}

	/**
	 * Data for the script (the numbers come with the Store API cart instead).
	 *
	 * @return array
	 */
	public function get_script_data() {
		return array();
	}
}
