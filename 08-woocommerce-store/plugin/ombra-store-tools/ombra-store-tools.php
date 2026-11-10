<?php
/**
 * Plugin Name:       Ombra Store Tools
 * Plugin URI:        https://github.com/bartnpu-droid/portfolio/tree/main/08-woocommerce-store
 * Description:       Store features for the Ombra demo shop: a live free shipping progress bar (cart, checkout, mini-cart, header), gift options at checkout, product badges and scent notes with their own blocks, and a settings tab under WooCommerce → Settings.
 * Version:           1.0.0
 * Requires at least: 6.7
 * Requires PHP:      8.1
 * Requires Plugins:  woocommerce
 * Author:            Ihor S.
 * License:           GPL-2.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       ombra-store-tools
 * WC requires at least: 10.0
 * WC tested up to:   11.2
 *
 * @package Ombra\StoreTools
 */

namespace Ombra\StoreTools;

defined( 'ABSPATH' ) || exit;

const VERSION = '1.0.0';
const FILE    = __FILE__;
const SLUG    = 'ombra-store-tools';

require_once __DIR__ . '/includes/class-settings.php';
require_once __DIR__ . '/includes/class-free-shipping.php';
require_once __DIR__ . '/includes/class-gift-options.php';
require_once __DIR__ . '/includes/class-product-fields.php';
require_once __DIR__ . '/includes/class-blocks.php';

/**
 * Declare compatibility with order storage (HPOS) and the Cart and Checkout blocks.
 */
add_action(
	'before_woocommerce_init',
	static function () {
		if ( class_exists( \Automattic\WooCommerce\Utilities\FeaturesUtil::class ) ) {
			\Automattic\WooCommerce\Utilities\FeaturesUtil::declare_compatibility( 'custom_order_tables', FILE, true );
			\Automattic\WooCommerce\Utilities\FeaturesUtil::declare_compatibility( 'cart_checkout_blocks', FILE, true );
		}
	}
);

/**
 * Start the plugin once WooCommerce is loaded.
 */
add_action(
	'plugins_loaded',
	static function () {
		if ( ! class_exists( 'WooCommerce' ) ) {
			return;
		}
		Settings::init();
		Free_Shipping::init();
		Gift_Options::init();
		Product_Fields::init();
		Blocks::init();
	}
);

/**
 * Settings link on the Plugins screen.
 */
add_filter(
	'plugin_action_links_' . plugin_basename( FILE ),
	static function ( $links ) {
		$url = admin_url( 'admin.php?page=wc-settings&tab=' . Settings::TAB );
		array_unshift( $links, '<a href="' . esc_url( $url ) . '">' . esc_html__( 'Settings', 'ombra-store-tools' ) . '</a>' );
		return $links;
	}
);
