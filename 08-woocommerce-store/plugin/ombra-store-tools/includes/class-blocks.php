<?php
/**
 * Registers the plugin's blocks.
 *
 * @package Ombra\StoreTools
 */

namespace Ombra\StoreTools;

defined( 'ABSPATH' ) || exit;

/**
 * Blocks: free shipping progress, product badge, scent notes.
 */
class Blocks {

	const EDITOR_HANDLE = 'ombra-store-tools-editor';

	/**
	 * Hooks.
	 */
	public static function init() {
		add_action( 'init', array( __CLASS__, 'register' ) );
	}

	/**
	 * Register the shared editor script, then each block from its block.json.
	 */
	public static function register() {
		wp_register_script(
			self::EDITOR_HANDLE,
			plugin_dir_url( FILE ) . 'assets/js/editor.js',
			array( 'wp-blocks', 'wp-element', 'wp-components', 'wp-block-editor', 'wp-server-side-render', 'wp-i18n' ),
			VERSION,
			array( 'in_footer' => true )
		);

		foreach ( array( 'free-shipping-progress', 'product-badge', 'scent-notes' ) as $block ) {
			register_block_type( dirname( FILE ) . '/blocks/' . $block );
		}
	}
}
