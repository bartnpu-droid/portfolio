<?php
/**
 * Product badge block.
 *
 * @package Ombra\StoreTools
 *
 * @var array    $attributes Block attributes.
 * @var WP_Block $block      Block instance (context: postId).
 */

use Ombra\StoreTools\Product_Fields;

defined( 'ABSPATH' ) || exit;

$ombra_product_id = (int) ( $block->context['postId'] ?? get_the_ID() );
$ombra_badge      = $ombra_product_id ? Product_Fields::badge( $ombra_product_id ) : null;
if ( ! $ombra_badge ) {
	return;
}

$ombra_variant = ( $attributes['variant'] ?? 'overlay' ) === 'inline' ? 'inline' : 'overlay';
$ombra_wrapper = get_block_wrapper_attributes(
	array( 'class' => 'ombra-badge ombra-badge--' . $ombra_badge['key'] . ' ombra-badge--' . $ombra_variant )
);
printf(
	'<span %1$s>%2$s</span>',
	$ombra_wrapper, // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped by get_block_wrapper_attributes().
	esc_html( $ombra_badge['label'] )
);
