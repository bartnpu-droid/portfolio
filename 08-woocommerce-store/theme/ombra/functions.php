<?php
/**
 * Ombra theme setup.
 *
 * Everything visual is in theme.json, templates, parts and patterns.
 * This file only loads the stylesheet and registers the pattern category.
 *
 * @package Ombra
 */

defined( 'ABSPATH' ) || exit;

/**
 * Theme supports and editor styles.
 */
function ombra_setup() {
	add_editor_style( 'assets/css/theme.css' );
	add_theme_support( 'wc-product-gallery-zoom' );
	add_theme_support( 'wc-product-gallery-lightbox' );
	add_theme_support( 'wc-product-gallery-slider' );
}
add_action( 'after_setup_theme', 'ombra_setup' );

/**
 * Front-end stylesheet: details that theme.json cannot express (header grid, cards, WooCommerce blocks).
 */
function ombra_enqueue() {
	wp_enqueue_style(
		'ombra',
		get_theme_file_uri( 'assets/css/theme.css' ),
		array(),
		wp_get_theme()->get( 'Version' )
	);
}
add_action( 'wp_enqueue_scripts', 'ombra_enqueue' );

/**
 * Pattern category for the theme's sections.
 */
function ombra_patterns() {
	register_block_pattern_category( 'ombra', array( 'label' => __( 'Ombra', 'ombra' ) ) );
}
add_action( 'init', 'ombra_patterns' );

/**
 * URL of a WooCommerce product category, or the shop page if the category does not exist yet.
 *
 * Patterns use this instead of fixed links, so the theme works under any site address
 * (a sub-folder, WordPress Playground, a staging domain).
 *
 * @param string $slug Category slug.
 * @return string
 */
function ombra_category_url( $slug ) {
	$link = taxonomy_exists( 'product_cat' ) ? get_term_link( $slug, 'product_cat' ) : '';
	if ( $link && ! is_wp_error( $link ) ) {
		return $link;
	}
	return ombra_shop_url();
}

/**
 * URL of the shop page.
 *
 * @return string
 */
function ombra_shop_url() {
	if ( function_exists( 'wc_get_page_permalink' ) ) {
		return wc_get_page_permalink( 'shop' );
	}
	return home_url( '/' );
}

/**
 * URL of a page by its slug, or the home page.
 *
 * @param string $slug Page slug.
 * @return string
 */
function ombra_page_url( $slug ) {
	$page = get_page_by_path( $slug );
	return $page ? get_permalink( $page ) : home_url( '/' );
}

/**
 * URL of a product by its slug, or the shop page.
 *
 * @param string $slug Product slug.
 * @return string
 */
function ombra_product_url( $slug ) {
	$product = get_page_by_path( $slug, OBJECT, 'product' );
	return $product ? get_permalink( $product ) : ombra_shop_url();
}

/**
 * URL of an image shipped with the theme.
 *
 * @param string $file File name in assets/images.
 * @return string
 */
function ombra_image( $file ) {
	return get_theme_file_uri( 'assets/images/' . $file );
}

/**
 * The header pattern already places the account icon and the mini-cart, so stop WooCommerce
 * from adding a second set next to the navigation (WooCommerce does that with block hooks).
 *
 * @param string[] $hooked_blocks Blocks hooked at this position.
 * @param string   $position      Position relative to the anchor.
 * @param string   $anchor_block  Anchor block name.
 * @return string[]
 */
function ombra_skip_hooked_header_blocks( $hooked_blocks, $position, $anchor_block ) {
	if ( 'core/navigation' === $anchor_block ) {
		return array_values( array_diff( $hooked_blocks, array( 'woocommerce/customer-account', 'woocommerce/mini-cart' ) ) );
	}
	return $hooked_blocks;
}
add_filter( 'hooked_block_types', 'ombra_skip_hooked_header_blocks', 20, 3 );

/**
 * Show whole prices without cents ("$34", but "$6.50").
 */
add_filter( 'woocommerce_price_trim_zeros', '__return_true' );
