<?php
/**
 * Free shipping progress: the numbers, and how they reach the page.
 *
 * One calculation on the server, shared by everything:
 * - the Store API cart response (extensions → ombra-store-tools), which the Cart and Checkout blocks read;
 * - the "Free shipping progress" block (first render, then the same Store API data after cart changes).
 *
 * @package Ombra\StoreTools
 */

namespace Ombra\StoreTools;

use Automattic\WooCommerce\StoreApi\Schemas\V1\CartSchema;

defined( 'ABSPATH' ) || exit;

/**
 * Free shipping bar.
 */
class Free_Shipping {

	const STORE_API_NAMESPACE = 'ombra-store-tools';

	/**
	 * Hooks.
	 */
	public static function init() {
		if ( did_action( 'woocommerce_blocks_loaded' ) ) {
			self::register_store_api_data();
		} else {
			add_action( 'woocommerce_blocks_loaded', array( __CLASS__, 'register_store_api_data' ) );
		}
		add_action( 'woocommerce_blocks_cart_block_registration', array( __CLASS__, 'register_integration' ) );
		add_action( 'woocommerce_blocks_checkout_block_registration', array( __CLASS__, 'register_integration' ) );
		add_filter( 'woocommerce_package_rates', array( __CLASS__, 'hide_paid_when_free' ), 100 );
		// Shipping rates are cached per cart; start fresh when the setting changes.
		add_action( 'update_option_ombra_fsb_hide_paid', array( __CLASS__, 'flush_shipping_cache' ) );
		add_action( 'add_option_ombra_fsb_hide_paid', array( __CLASS__, 'flush_shipping_cache' ) );
	}

	/**
	 * Invalidate WooCommerce's cached shipping rates.
	 */
	public static function flush_shipping_cache() {
		\WC_Cache_Helper::get_transient_version( 'shipping', true );
	}

	/**
	 * Once free shipping is available, offer only that (and local pickup).
	 *
	 * Without this WooCommerce keeps the paid rate selected, so a customer over the goal
	 * could still pay for shipping without noticing.
	 *
	 * @param \WC_Shipping_Rate[] $rates Rates for a package.
	 * @return \WC_Shipping_Rate[]
	 */
	public static function hide_paid_when_free( $rates ) {
		if ( ! Settings::is_on( 'ombra_fsb_hide_paid' ) ) {
			return $rates;
		}
		$has_free = false;
		foreach ( $rates as $rate ) {
			if ( 'free_shipping' === $rate->get_method_id() ) {
				$has_free = true;
				break;
			}
		}
		if ( ! $has_free ) {
			return $rates;
		}
		return array_filter(
			$rates,
			static function ( $rate ) {
				return in_array( $rate->get_method_id(), array( 'free_shipping', 'local_pickup', 'pickup_location' ), true );
			}
		);
	}

	/**
	 * Add our numbers to the Store API cart response.
	 */
	public static function register_store_api_data() {
		if ( ! function_exists( 'woocommerce_store_api_register_endpoint_data' ) ) {
			return;
		}
		woocommerce_store_api_register_endpoint_data(
			array(
				'endpoint'        => CartSchema::IDENTIFIER,
				'namespace'       => self::STORE_API_NAMESPACE,
				'data_callback'   => array( __CLASS__, 'data' ),
				'schema_callback' => array( __CLASS__, 'schema' ),
				'schema_type'     => ARRAY_A,
			)
		);
	}

	/**
	 * Load the cart/checkout script through the blocks integration registry.
	 *
	 * @param \Automattic\WooCommerce\Blocks\Integrations\IntegrationRegistry $registry Registry.
	 */
	public static function register_integration( $registry ) {
		require_once __DIR__ . '/class-blocks-integration.php';
		if ( ! $registry->is_registered( Blocks_Integration::NAME ) ) {
			$registry->register( new Blocks_Integration() );
		}
	}

	/**
	 * Free shipping goal in the store currency.
	 *
	 * With "method" as the source, the goal is the minimum order amount of the Free shipping method
	 * in the shipping zone that matches the customer's address (or the store's base country).
	 *
	 * @return float
	 */
	public static function goal() {
		$custom = (float) Settings::get( 'ombra_fsb_goal' );
		if ( 'method' !== Settings::get( 'ombra_fsb_goal_source' ) ) {
			return max( 0.0, $custom );
		}
		$method = self::free_shipping_method();
		if ( $method ) {
			return (float) $method->get_option( 'min_amount', $custom );
		}
		return max( 0.0, $custom );
	}

	/**
	 * The enabled Free shipping method with a minimum amount, for the customer's zone.
	 *
	 * @return \WC_Shipping_Free_Shipping|null
	 */
	public static function free_shipping_method() {
		if ( ! class_exists( 'WC_Shipping_Zones' ) ) {
			return null;
		}
		$customer = WC()->customer;
		$package  = array(
			'destination' => array(
				'country'  => $customer && $customer->get_shipping_country() ? $customer->get_shipping_country() : WC()->countries->get_base_country(),
				'state'    => $customer ? $customer->get_shipping_state() : WC()->countries->get_base_state(),
				'postcode' => $customer ? $customer->get_shipping_postcode() : WC()->countries->get_base_postcode(),
			),
		);
		$zone     = \WC_Shipping_Zones::get_zone_matching_package( $package );
		foreach ( $zone->get_shipping_methods( true ) as $method ) {
			if ( 'free_shipping' === $method->id && in_array( $method->get_option( 'requires' ), array( 'min_amount', 'either' ), true ) ) {
				return $method;
			}
		}
		return null;
	}

	/**
	 * Short note for the settings screen: what the "method" source currently resolves to.
	 *
	 * @return string
	 */
	public static function method_goal_note() {
		if ( ! function_exists( 'WC' ) || ! WC()->countries ) {
			return '';
		}
		$method = self::free_shipping_method();
		if ( ! $method ) {
			return __( 'No Free shipping method with a minimum amount was found for the store country, so the amount below is used.', 'ombra-store-tools' );
		}
		return sprintf(
			/* translators: %s: amount */
			__( 'Right now this is %s, from WooCommerce → Settings → Shipping.', 'ombra-store-tools' ),
			self::money( (float) $method->get_option( 'min_amount' ) )
		);
	}

	/**
	 * Cart amount that counts towards the goal, the same way WooCommerce's Free shipping method counts it.
	 *
	 * @return float
	 */
	public static function cart_amount() {
		$cart = WC()->cart;
		if ( ! $cart ) {
			return 0.0;
		}
		// Same steps as WC_Shipping_Free_Shipping::is_available().
		$amount = (float) $cart->get_displayed_subtotal();
		if ( $cart->display_prices_including_tax() ) {
			$amount -= (float) $cart->get_discount_tax();
		}
		$method = self::free_shipping_method();
		if ( ! $method || 'yes' !== $method->get_option( 'ignore_discounts' ) ) {
			$amount -= (float) $cart->get_discount_total();
		}
		return max( 0.0, round( $amount, wc_get_price_decimals() ) );
	}

	/**
	 * Everything the bar needs, for the current cart.
	 *
	 * @return array
	 */
	public static function data() {
		$enabled  = Settings::is_on( 'ombra_fsb_enabled' );
		$goal     = self::goal();
		$cart     = WC()->cart;
		$is_empty = ! $cart || $cart->is_empty();
		$amount   = $is_empty ? 0.0 : self::cart_amount();
		$left     = max( 0.0, $goal - $amount );
		$unlocked = ! $is_empty && $goal > 0 && $left <= 0;
		$progress = $goal > 0 ? min( 1, $amount / $goal ) : 1;

		if ( $is_empty ) {
			$message = str_replace( '[goal]', self::money( $goal ), Settings::get( 'ombra_fsb_message_empty' ) );
		} elseif ( $unlocked ) {
			$message = Settings::get( 'ombra_fsb_message_done' );
		} else {
			$message = str_replace( '[amount]', self::money( $left ), Settings::get( 'ombra_fsb_message_progress' ) );
		}

		return array(
			'enabled'   => $enabled && $goal > 0,
			'is_empty'  => $is_empty,
			'unlocked'  => $unlocked,
			'goal'      => self::minor_units( $goal ),
			'amount'    => self::minor_units( $amount ),
			'remaining' => self::minor_units( $left ),
			'progress'  => round( $progress, 4 ),
			'message'   => wp_strip_all_tags( $message ),
			'color'     => sanitize_hex_color( Settings::get( 'ombra_fsb_bar_color' ) ) ?: '#a24e2b',
		);
	}

	/**
	 * Store API schema for our data.
	 *
	 * @return array
	 */
	public static function schema() {
		$readonly = array(
			'context'  => array( 'view', 'edit' ),
			'readonly' => true,
		);
		return array(
			'enabled'   => array( 'description' => __( 'Whether the bar is shown.', 'ombra-store-tools' ), 'type' => 'boolean' ) + $readonly,
			'is_empty'  => array( 'description' => __( 'Whether the cart is empty.', 'ombra-store-tools' ), 'type' => 'boolean' ) + $readonly,
			'unlocked'  => array( 'description' => __( 'Whether the cart qualifies for free shipping.', 'ombra-store-tools' ), 'type' => 'boolean' ) + $readonly,
			'goal'      => array( 'description' => __( 'Goal in minor units.', 'ombra-store-tools' ), 'type' => 'integer' ) + $readonly,
			'amount'    => array( 'description' => __( 'Amount counted towards the goal, in minor units.', 'ombra-store-tools' ), 'type' => 'integer' ) + $readonly,
			'remaining' => array( 'description' => __( 'Amount left, in minor units.', 'ombra-store-tools' ), 'type' => 'integer' ) + $readonly,
			'progress'  => array( 'description' => __( 'Progress from 0 to 1.', 'ombra-store-tools' ), 'type' => 'number' ) + $readonly,
			'message'   => array( 'description' => __( 'Message to show, plain text.', 'ombra-store-tools' ), 'type' => 'string' ) + $readonly,
			'color'     => array( 'description' => __( 'Bar colour.', 'ombra-store-tools' ), 'type' => 'string' ) + $readonly,
		);
	}

	/**
	 * Price as plain text in the store format, e.g. "$12.00".
	 *
	 * @param float $amount Amount.
	 * @return string
	 */
	public static function money( $amount ) {
		// Whole amounts read better without cents: "$75", but "$12.50".
		$decimals = abs( $amount - round( $amount ) ) < 0.005 ? 0 : wc_get_price_decimals();
		return html_entity_decode( wp_strip_all_tags( wc_price( $amount, array( 'decimals' => $decimals ) ) ), ENT_QUOTES, 'UTF-8' );
	}

	/**
	 * Amount in minor units (cents), like the Store API.
	 *
	 * @param float $amount Amount.
	 * @return int
	 */
	private static function minor_units( $amount ) {
		return (int) round( $amount * ( 10 ** wc_get_price_decimals() ) );
	}
}
