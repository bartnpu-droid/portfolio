<?php
/**
 * Checks for the Ombra Store Tools plugin, run against a site with the demo store installed:
 *
 *     wp eval-file tests/run-tests.php
 *
 * Builds real carts with WooCommerce's own classes and checks the free shipping numbers,
 * the shipping rates offered, the gift note rules and the product badges.
 *
 * @package Ombra\StoreTools
 */

use Ombra\StoreTools\Free_Shipping;
use Ombra\StoreTools\Gift_Options;
use Ombra\StoreTools\Product_Fields;

defined( 'ABSPATH' ) || exit;

// wp eval-file runs this file inside a function, so the counters live in $GLOBALS explicitly.
$GLOBALS['ombra_failed'] = 0;
$GLOBALS['ombra_passed'] = 0;

/**
 * Record one check.
 *
 * @param string $name     What is checked.
 * @param mixed  $actual   Actual value.
 * @param mixed  $expected Expected value.
 */
function ombra_check( $name, $actual, $expected ) {
	global $ombra_failed, $ombra_passed;
	if ( $actual === $expected ) {
		++$ombra_passed;
		WP_CLI::log( "  ok    $name" );
		return;
	}
	++$ombra_failed;
	WP_CLI::log( "  FAIL  $name: expected " . var_export( $expected, true ) . ', got ' . var_export( $actual, true ) );
}

/**
 * Product ID by slug.
 *
 * @param string $slug Slug.
 * @return int
 */
function ombra_test_product( $slug ) {
	$post = get_page_by_path( $slug, OBJECT, 'product' );
	if ( ! $post ) {
		WP_CLI::error( "Demo product $slug not found. Run playground/setup.php first." );
	}
	return (int) $post->ID;
}

/**
 * A fresh cart for a guest in the store's country.
 */
function ombra_fresh_cart() {
	WC()->frontend_includes();
	WC()->session = new WC_Session_Handler();
	WC()->session->init();
	WC()->customer = new WC_Customer( 0, true );
	WC()->customer->set_shipping_country( 'US' );
	WC()->customer->set_shipping_state( 'NY' );
	WC()->customer->set_shipping_postcode( '12207' );
	WC()->cart = new WC_Cart();
	WC()->cart->empty_cart();
}

/**
 * The 200 g variation of a candle.
 *
 * @param int $product_id Variable product ID.
 * @return array{0: int, 1: array}
 */
function ombra_variation_200( $product_id ) {
	$product = wc_get_product( $product_id );
	foreach ( $product->get_children() as $child_id ) {
		$child = wc_get_product( $child_id );
		if ( '200-g' === $child->get_attributes()['pa_size'] ) {
			return array( $child_id, array( 'attribute_pa_size' => '200-g' ) );
		}
	}
	WP_CLI::error( 'No 200 g variation.' );
}

update_option( 'ombra_fsb_goal_source', 'method' );
update_option( 'ombra_fsb_hide_paid', 'yes' );

$ombra_fig     = ombra_test_product( 'fig-cedar-candle' );
$ombra_matches = ombra_test_product( 'long-matches' );
list( $ombra_fig_200, $ombra_fig_attrs ) = ombra_variation_200( $ombra_fig );

WP_CLI::log( 'Free shipping bar' );
ombra_fresh_cart();
$ombra_data = Free_Shipping::data();
ombra_check( 'goal comes from the Free shipping method ($75)', $ombra_data['goal'], 7500 );
ombra_check( 'empty cart is reported as empty', $ombra_data['is_empty'], true );
ombra_check( 'empty cart message', $ombra_data['message'], 'Free shipping on orders over $75' );

WC()->cart->add_to_cart( $ombra_fig, 1, $ombra_fig_200, $ombra_fig_attrs );
WC()->cart->calculate_totals();
$ombra_data = Free_Shipping::data();
ombra_check( 'one 200 g candle: $41 left', $ombra_data['remaining'], 4100 );
ombra_check( 'one 200 g candle: message', $ombra_data['message'], "You're \$41 away from free shipping" );
ombra_check( 'one 200 g candle: progress', $ombra_data['progress'], round( 34 / 75, 4 ) );

WC()->cart->set_quantity( array_key_first( WC()->cart->get_cart() ), 2 );
WC()->cart->calculate_totals();
$ombra_data = Free_Shipping::data();
ombra_check( 'two candles: $7 left', $ombra_data['remaining'], 700 );
ombra_check( 'two candles: not unlocked yet', $ombra_data['unlocked'], false );

WC()->cart->add_to_cart( $ombra_matches, 1 );
WC()->cart->calculate_totals();
$ombra_data = Free_Shipping::data();
ombra_check( 'over $75: unlocked', $ombra_data['unlocked'], true );
ombra_check( 'over $75: message', $ombra_data['message'], 'Your order ships free' );
ombra_check( 'over $75: progress capped at 1', (float) $ombra_data['progress'], 1.0 );

WP_CLI::log( 'Shipping rates' );
WC()->cart->calculate_shipping();
$ombra_rates = array();
foreach ( WC()->shipping()->get_packages() as $ombra_package ) {
	foreach ( $ombra_package['rates'] as $ombra_rate ) {
		$ombra_rates[] = $ombra_rate->get_method_id();
	}
}
ombra_check( 'over $75: only free shipping is offered', $ombra_rates, array( 'free_shipping' ) );

update_option( 'ombra_fsb_hide_paid', 'no' );
WC()->cart->calculate_shipping();
$ombra_rates = array();
foreach ( WC()->shipping()->get_packages() as $ombra_package ) {
	foreach ( $ombra_package['rates'] as $ombra_rate ) {
		$ombra_rates[] = $ombra_rate->get_method_id();
	}
}
sort( $ombra_rates );
ombra_check( 'setting off: paid rate offered too', $ombra_rates, array( 'flat_rate', 'free_shipping' ) );
update_option( 'ombra_fsb_hide_paid', 'yes' );

WP_CLI::log( 'Coupons count like WooCommerce counts them' );
$ombra_coupon = new WC_Coupon();
$ombra_coupon->set_code( 'ombra-test-10' );
$ombra_coupon->set_discount_type( 'percent' );
$ombra_coupon->set_amount( 10 );
$ombra_coupon->save();
WC()->cart->apply_coupon( 'ombra-test-10' );
WC()->cart->calculate_totals();
$ombra_data = Free_Shipping::data();
ombra_check( '$82 minus 10%: $73.80 counts, $1.20 left', $ombra_data['remaining'], 120 );
ombra_check( '$82 minus 10%: message with cents', $ombra_data['message'], "You're \$1.20 away from free shipping" );
$ombra_coupon->delete( true );

update_option( 'ombra_fsb_goal_source', 'custom' );
update_option( 'ombra_fsb_goal', '100' );
WC()->cart->remove_coupons();
WC()->cart->calculate_totals();
$ombra_data = Free_Shipping::data();
ombra_check( 'custom goal $100: $18 left', $ombra_data['remaining'], 1800 );
update_option( 'ombra_fsb_goal_source', 'method' );
update_option( 'ombra_fsb_goal', '75' );
WC()->cart->empty_cart();

WP_CLI::log( 'Gift note' );
ombra_check( 'note is one clean line', Gift_Options::sanitize_note( "  Happy   birthday,\n Ana!  " ), 'Happy birthday, Ana!' );
ombra_check( 'short note passes', Gift_Options::validate_note( 'Happy birthday, Ana!' ), true );
ombra_check( 'long note is stopped', is_wp_error( Gift_Options::validate_note( str_repeat( 'a', Gift_Options::note_length() + 1 ) ) ), true );
ombra_check( 'limit comes from the settings', Gift_Options::note_length(), (int) get_option( 'ombra_gift_note_length', 160 ) );

WP_CLI::log( 'Badges and scent notes' );
ombra_check( 'Fig & Cedar shows Bestseller', Product_Fields::badge( $ombra_fig )['label'] ?? null, 'Bestseller' );
ombra_check( 'room spray on sale shows Sale', Product_Fields::badge( ombra_test_product( 'room-spray' ) )['key'] ?? null, 'sale' );
ombra_check( 'matches have no badge', Product_Fields::badge( $ombra_matches ), null );
ombra_check( 'scent notes are read from the product', Product_Fields::notes( $ombra_fig )['base'] ?? null, 'Cedarwood, vetiver' );

WP_CLI::log( '' );
if ( $GLOBALS['ombra_failed'] ) {
	WP_CLI::error( $GLOBALS['ombra_failed'] . ' failed, ' . $GLOBALS['ombra_passed'] . ' passed.' );
}
WP_CLI::success( 'All ' . $GLOBALS['ombra_passed'] . ' checks passed.' );
